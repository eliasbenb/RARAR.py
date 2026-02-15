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
    _last_block_type: int | None = None

    def _find_rar_marker(self) -> int:
        """Find the RAR5 marker in the file.

        Returns:
            int: Position of the RAR marker in the file

        Raises:
            RarMarkerNotFoundError: If the RAR marker is not found
        """
        # First try to find marker in the first chunk
        first_chunk_size = 8192
        chunk = self.read_bytes(0, first_chunk_size)
        marker_pos = chunk.find(self.RAR_MARKER_SIG)
        if marker_pos != -1:
            logger.debug("RAR5 marker found at position %s", marker_pos)
            return marker_pos

        position = first_chunk_size - len(self.RAR_MARKER_SIG) + 1
        max_search = MAX_SEARCH_SIZE

        logger.debug("Searching for RAR5 marker in first %s bytes", max_search)
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
                        "RAR5 marker found at position %s", position + marker_pos
                    )
                    return position + marker_pos

                # Move forward by chunk size minus marker length
                # to ensure we don't miss it if it spans chunks
                position += max(1, len(chunk) - len(self.RAR_MARKER_SIG) + 1)

            except Exception as e:
                logger.error("Error while searching for RAR5 marker: %s", e)
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
        data = self.read_bytes(position, 10)
        if not data:
            return 0, 0
        return self._read_vint_from_bytes(data)

    def _parse_file_header(self, position: int) -> tuple[RarFile | None, int]:
        """Parse a file header block and return the file info and next position.

        Args:
            position (int): Starting position of the file header

        Returns:
            tuple[RarFile | None, int]: Tuple of (file_info, next_position)
        """
        try:
            logger.debug("Parsing RAR5 file header at position %s", position)

            prefix = self.read_bytes(position, 14)  # CRC32 + max VINT length
            if len(prefix) < 5:
                logger.error("Not enough data for header prefix")
                return None, position

            header_size, vint_size = self._read_vint_from_bytes(prefix[4:])
            if vint_size <= 0:
                return None, position

            header_start_pos = position + 4 + vint_size
            block_size = 4 + vint_size + header_size
            block = (
                prefix
                if len(prefix) >= block_size
                else self.read_bytes(position, block_size)
            )
            if len(block) < block_size:
                return None, position

            cursor = 4 + vint_size

            header_type, read_size = self._read_vint_from_bytes(block[cursor:])
            if read_size <= 0:
                return None, position
            cursor += read_size
            self._last_block_type = header_type

            header_flags, read_size = self._read_vint_from_bytes(block[cursor:])
            if read_size <= 0:
                return None, position
            cursor += read_size

            if header_flags & RAR5_BLOCK_FLAG_EXTRA_DATA:
                _extra_area_size, read_size = self._read_vint_from_bytes(block[cursor:])
                if read_size <= 0:
                    return None, position
                cursor += read_size

            data_size = 0
            if header_flags & RAR5_BLOCK_FLAG_DATA_AREA:
                data_size, read_size = self._read_vint_from_bytes(block[cursor:])
                if read_size <= 0:
                    return None, position
                cursor += read_size

            next_position = header_start_pos + header_size + data_size

            if header_type != RAR5_BLOCK_FILE:
                logger.debug("Not a file header (type: %s), skipping", header_type)
                return None, next_position

            file_flags, read_size = self._read_vint_from_bytes(block[cursor:])
            if read_size <= 0:
                return None, position
            cursor += read_size

            unpacked_size, read_size = self._read_vint_from_bytes(block[cursor:])
            if read_size <= 0:
                return None, position
            cursor += read_size

            _attributes, read_size = self._read_vint_from_bytes(block[cursor:])
            if read_size <= 0:
                return None, position
            cursor += read_size

            if file_flags & RAR5_FILE_FLAG_HAS_MTIME:
                if cursor + 4 > len(block):
                    return None, position
                cursor += 4

            crc32_value = 0
            if file_flags & RAR5_FILE_FLAG_HAS_CRC32:
                if cursor + 4 > len(block):
                    return None, position
                crc32_value = struct.unpack_from("<I", block, cursor)[0]
                cursor += 4

            compression_info, read_size = self._read_vint_from_bytes(block[cursor:])
            if read_size <= 0:
                return None, position
            cursor += read_size

            _host_os, read_size = self._read_vint_from_bytes(block[cursor:])
            if read_size <= 0:
                return None, position
            cursor += read_size

            name_length, read_size = self._read_vint_from_bytes(block[cursor:])
            if read_size <= 0:
                return None, position
            cursor += read_size

            name_end = cursor + name_length
            if name_end > len(block):
                logger.error("Not enough data for filename")
                return None, position

            filename = block[cursor:name_end].decode("utf-8", "replace")

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

            logger.debug(
                "File header parsed: %s (size: %s, compressed: %s, next position: %s)",
                filename,
                unpacked_size,
                data_size,
                next_position,
            )
            return file_info, next_position

        except Exception as e:
            logger.error("Error parsing file header at position %s: %s", position, e)
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
                header_crc_data = self.read_bytes(pos, 4)
                if len(header_crc_data) < 4:
                    logger.debug("Reached end of file (incomplete header CRC)")
                    break
                file_info, next_pos = self._parse_file_header(pos)
                if next_pos <= pos:
                    logger.debug("Parser did not advance position (%s), stopping", pos)
                    break

                if self._last_block_type == RAR5_BLOCK_END:
                    logger.debug("Found end of archive marker")
                    break

                if file_info:
                    yield file_info

                pos = next_pos

            except Exception as e:
                logger.error("Error while processing RAR5 blocks: %s", e)
                logger.debug("Position at error: %s", pos)
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
