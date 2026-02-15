"""RAR5 format reader."""

import logging
import struct
from collections.abc import Generator
from pathlib import Path

from rarar.const import (
    MAX_SEARCH_SIZE,
    RAR5_BLOCK_END,
    RAR5_BLOCK_FILE,
    RAR5_BLOCK_FLAG_DATA_AREA,
    RAR5_BLOCK_FLAG_EXTRA_DATA,
    RAR5_COMPRESSION_METHODS_REVERSE,
    RAR5_FILE_FLAG_DIRECTORY,
    RAR5_FILE_FLAG_HAS_CRC32,
    RAR5_FILE_FLAG_HAS_MTIME,
    RAR5_MARKER,
)
from rarar.exceptions import (
    DirectoryExtractNotSupportedError,
    RarMarkerNotFoundError,
)
from rarar.models import RarFile
from rarar.reader.base import RarReaderBase

logger = logging.getLogger("rarar")


class Rar5Reader(RarReaderBase):
    """Reader for RAR 5.0 format archives."""

    RAR_MARKER_SIG = RAR5_MARKER

    def _find_rar_marker(self) -> int:
        """Find the RAR5 marker in the file.

        Returns:
            int: Position of the RAR marker in the file

        Raises:
            RarMarkerNotFoundError: If the RAR marker is not found
        """
        position = 0
        max_search = MAX_SEARCH_SIZE

        logger.debug(f"Searching for RAR5 marker in first {max_search} bytes")
        while position < max_search:
            try:
                chunk = self.read_bytes(
                    position, min(self.chunk_size, max_search - position)
                )
                if not chunk:
                    break

                marker_pos = chunk.find(self.RAR_MARKER_SIG)
                if marker_pos != -1:
                    logger.debug(
                        f"RAR5 marker found at position {position + marker_pos}"
                    )
                    return position + marker_pos

                # Move forward by chunk size minus marker length
                # to ensure we don't miss it if it spans chunks
                position += max(1, len(chunk) - len(self.RAR_MARKER_SIG) + 1)

            except Exception as e:
                logger.error(f"Error while searching for RAR5 marker: {e}")
                raise

        logger.error("RAR5 marker not found within search limit")
        raise RarMarkerNotFoundError("RAR5 marker not found within search limit")

    def _read_vint(self, position: int) -> tuple[int, int]:
        """Read a variable-length integer from the given position.

        Args:
            position (int): Position to read from

        Returns:
            tuple[int, int]: (value, bytes_read)
        """
        result = 0
        bytes_read = 0
        shift = 0

        while True:
            byte = self.read_bytes(position + bytes_read, 1)[0]
            bytes_read += 1

            # Add 7 bits from the current byte to the result
            result |= (byte & 0x7F) << shift
            shift += 7

            # If the highest bit is not set, this is the last byte
            if not (byte & 0x80):
                break

            # Variable length integers are limited to 10 bytes in RAR5
            if bytes_read >= 10:
                logger.warning("Variable-length integer exceeded 10 bytes")
                break

        return result, bytes_read

    def _parse_file_header(self, position: int) -> tuple[RarFile | None, int]:
        """Parse a file header block and return the file info and next position.

        Args:
            position (int): Starting position of the file header

        Returns:
            tuple[RarFile | None, int]: Tuple of (file_info, next_position)
        """
        try:
            logger.debug(f"Parsing RAR5 file header at position {position}")

            header_crc_data = self.read_bytes(position, 4)
            if len(header_crc_data) < 4:
                logger.error("Not enough data for header CRC")
                return None, position
            _header_crc = struct.unpack("<I", header_crc_data)[0]
            position += 4

            # Read header size - this is the size of everything after this field
            header_size, vint_size = self._read_vint(position)
            position += vint_size
            header_start_pos = position

            header_type, vint_size = self._read_vint(position)
            position += vint_size

            # If not a file header, skip it
            if header_type != RAR5_BLOCK_FILE:
                logger.debug(f"Not a file header (type: {header_type}), skipping")
                # Skip to the end of this header
                next_position = (
                    header_start_pos + header_size
                )  # position after header size field + header size
                return None, next_position

            header_flags, vint_size = self._read_vint(position)
            position += vint_size

            _extra_area_size = 0
            if header_flags & RAR5_BLOCK_FLAG_EXTRA_DATA:
                _extra_area_size, vint_size = self._read_vint(position)
                position += vint_size

            data_size = 0
            if header_flags & RAR5_BLOCK_FLAG_DATA_AREA:
                data_size, vint_size = self._read_vint(position)
                position += vint_size

            file_flags, vint_size = self._read_vint(position)
            position += vint_size

            unpacked_size, vint_size = self._read_vint(position)
            position += vint_size

            _, vint_size = self._read_vint(position)
            position += vint_size

            _mtime = None
            if file_flags & RAR5_FILE_FLAG_HAS_MTIME:
                mtime_data = self.read_bytes(position, 4)
                if len(mtime_data) >= 4:
                    _mtime = struct.unpack("<I", mtime_data)[0]
                    position += 4

            crc32_value = 0
            if file_flags & RAR5_FILE_FLAG_HAS_CRC32:
                crc32_data = self.read_bytes(position, 4)
                if len(crc32_data) >= 4:
                    crc32_value = struct.unpack("<I", crc32_data)[0]
                    position += 4

            compression_info, vint_size = self._read_vint(position)
            position += vint_size

            _host_os, vint_size = self._read_vint(position)
            position += vint_size

            name_length, vint_size = self._read_vint(position)
            position += vint_size

            filename_data = self.read_bytes(position, name_length)
            if len(filename_data) < name_length:
                logger.error("Not enough data for filename")
                return None, position
            filename = filename_data.decode("utf-8", "replace")
            position += name_length

            is_directory = (file_flags & RAR5_FILE_FLAG_DIRECTORY) != 0

            compression_method = (compression_info >> 7) & 0x07

            data_offset = header_start_pos + header_size
            file_info = RarFile(
                path=Path(filename),
                size=unpacked_size,
                compressed_size=data_size,
                method=compression_method,
                crc=crc32_value,
                is_directory=is_directory,
                data_offset=data_offset,
                next_offset=data_offset + data_size,
            )

            # Skip to next header
            next_position = header_start_pos + header_size
            if header_flags & RAR5_BLOCK_FLAG_DATA_AREA:
                next_position += data_size

            logger.debug(
                f"File header parsed: {filename} (size: {unpacked_size}, "
                f"compressed: {data_size}, next position: {next_position})"
            )
            return file_info, next_position

        except Exception as e:
            logger.error(f"Error parsing file header at position {position}: {e}")
            import traceback

            logger.debug(traceback.format_exc())
            return None, position

    def _read_vint_from_bytes(self, data: bytes) -> tuple[int, int]:
        """Read a variable-length integer from byte array.

        Args:
            data (bytes): Byte array to read from

        Returns:
            tuple[int, int]: (value, bytes_read)
        """
        result = 0
        bytes_read = 0
        shift = 0

        while bytes_read < len(data):
            byte = data[bytes_read]
            bytes_read += 1

            # Add 7 bits from the current byte to the result
            result |= (byte & 0x7F) << shift
            shift += 7

            # If the highest bit is not set, this is the last byte
            if not (byte & 0x80):
                break

            # Variable length integers are limited to 10 bytes in RAR5
            if bytes_read >= 10:
                logger.warning("Variable-length integer exceeded 10 bytes")
                break

        return result, bytes_read

    def generate_files(self) -> Generator[RarFile, None, None]:
        """Generate RarFile objects for each file in the archive.

        Yields:
            RarFile: RarFile objects in the archive one by one

        Raises:
            RarMarkerNotFoundError: If the RAR marker is not found
            InvalidRarFormatError: If the archive format is invalid
        """
        pos = self._rar_marker
        pos += len(RAR5_MARKER)  # Skip marker block

        logger.debug("Processing RAR5 blocks...")
        while True:
            try:
                orig_pos = pos

                # Read header CRC32
                header_crc_data = self.read_bytes(pos, 4)
                if len(header_crc_data) < 4:
                    logger.debug("Reached end of file (incomplete header CRC)")
                    break
                _header_crc = struct.unpack("<I", header_crc_data)[0]
                pos += 4

                # Read header size - this is the size of everything after this field
                header_size, vint_size = self._read_vint(pos)
                pos += vint_size
                header_start_pos = pos  # This is where header size starts counting from

                # Read header type
                header_type, vint_type_size = self._read_vint(pos)
                pos += vint_type_size

                # Read header flags
                header_flags, vint_flags_size = self._read_vint(pos)
                pos += vint_flags_size

                logger.debug(
                    f"Found block type {header_type} at position {orig_pos}, "
                    f"flags: 0x{header_flags:x}"
                )

                # Calculate position after this header
                next_pos = header_start_pos + header_size  # After the header

                # If there's extra area size (not needed for positioning
                # as it's included in header_size)
                if header_flags & RAR5_BLOCK_FLAG_EXTRA_DATA:
                    _, vint_extra_size = self._read_vint(pos)
                    pos += vint_extra_size

                # If there's data area size
                if header_flags & RAR5_BLOCK_FLAG_DATA_AREA:
                    data_size, vint_data_size = self._read_vint(pos)
                    pos += vint_data_size
                    next_pos += data_size  # Add data size to next position

                if header_type == RAR5_BLOCK_END:
                    logger.debug("Found end of archive marker")
                    break

                if header_type == RAR5_BLOCK_FILE:
                    # Reset position to start of header
                    file_header_pos = orig_pos
                    file_info, file_next_pos = self._parse_file_header(file_header_pos)
                    if file_info:
                        yield file_info
                    pos = file_next_pos
                else:
                    # Skip other block types
                    logger.debug(
                        f"Skipping non-file block type {header_type}, moving to "
                        f"position {next_pos}"
                    )
                    pos = next_pos

            except Exception as e:
                logger.error(f"Error while processing RAR5 blocks: {e}")
                logger.debug(f"Position at error: {pos}")
                import traceback

                logger.debug(traceback.format_exc())
                break

    def read_file(self, file_info: RarFile) -> bytes:
        """Returns the raw file data for a given RarFile object.

        Args:
            file_info (RarFile): RarFile object to read

        Returns:
            bytes: Raw file data

        Raises:
            DirectoryExtractNotSupportedError: If the file is a directory
            CompressionNotSupportedError: If the file uses compression
        """
        if file_info.is_directory:
            raise DirectoryExtractNotSupportedError(
                f"Directory extracts are not supported: {file_info.path}"
            )

        logger.info(
            f"Reading file: {file_info.path} "
            f"({file_info.data_offset}-{file_info.next_offset - 1}) "
            f"({file_info.compressed_size} bytes)"
        )

        if file_info.method == RAR5_COMPRESSION_METHODS_REVERSE["Store"]:
            return self.read_bytes(file_info.data_offset, file_info.compressed_size)
        else:
            return self._decompress_file(file_info)
