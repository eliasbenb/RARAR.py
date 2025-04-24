import io
import logging
import struct
from typing import Generator

from ..const import (
    COMPRESSION_METHODS,
    COMPRESSION_METHODS_REVERSE,
    FLAG_DIRECTORY,
    FLAG_HAS_DATA,
    FLAG_HAS_HIGH_SIZE,
    FLAG_HAS_UNICODE_NAME,
    MAX_SEARCH_SIZE,
    RAR3_BLOCK_END,
    RAR3_BLOCK_FILE,
    RAR3_BLOCK_HEADER,
    RAR3_MARKER,
)
from ..exceptions import (
    CompressionNotSupportedError,
    DirectoryDownloadNotSupportedError,
    InvalidRarFormatError,
    RarMarkerNotFoundError,
)
from ..models import RarFile
from .base import RarReaderBase

logger = logging.getLogger("rarar")


class Rar3Reader(RarReaderBase):
    """Reader for RAR 4.x format archives."""

    def _find_rar_marker(self) -> int:
        """Find the RAR3 marker in the file using small chunk requests.

        Returns:
            int: Position of the RAR marker in the file

        Raises:
            RarMarkerNotFoundError: If the RAR marker is not found
        """
        position = 0
        max_search = MAX_SEARCH_SIZE

        logger.debug(f"Searching for RAR3 marker in first {max_search} bytes")
        while position < max_search:
            try:
                chunk = self.read_bytes(
                    position, min(self.chunk_size, max_search - position)
                )
                if not chunk:
                    break

                marker_pos = chunk.find(RAR3_MARKER)
                if marker_pos != -1:
                    logger.debug(
                        f"RAR3 marker found at position {position + marker_pos}"
                    )
                    return position + marker_pos

                # Move forward by chunk size minus the marker length to ensure we don't miss it
                # if it spans two chunks
                position += max(1, len(chunk) - len(RAR3_MARKER) + 1)

            except Exception:
                logger.error("Error while searching for RAR3 marker", exc_info=True)
                raise

        logger.error("RAR3 marker not found within search limit")
        raise RarMarkerNotFoundError("RAR3 marker not found within search limit")

    def _parse_file_header(self, position: int) -> tuple[RarFile | None, int]:
        """Parse a RAR3 file header block and return the file info and next position.

        Args:
            position (int): Starting position of the file header

        Returns:
            tuple[RarFile | None, int]: Tuple of (file_info, next_position)
        """
        head_size = 7  # Default size for header
        logger.debug(f"Parsing RAR3 file header at position {position}")

        # TODO: OS-independent path parsing
        try:
            # Read just the header basics first (7 bytes)
            header_data = self.read_bytes(position, 7)

            # Extract basic header fields
            _head_crc, head_type, head_flags = struct.unpack("<HBH", header_data[:5])
            head_size = struct.unpack("<H", header_data[5:7])[0]

            # If not a file block, skip it
            if head_type != RAR3_BLOCK_FILE:
                logger.debug(f"Not a file block (type: {head_type}), skipping")
                return None, position + head_size

            # Read the rest of the header, not the file data
            file_header_data = self.read_bytes(position + 7, head_size - 7)
            reader = io.BytesIO(file_header_data)

            # Parse file header fields
            pack_size = struct.unpack("<I", reader.read(4))[0]
            unp_size = struct.unpack("<I", reader.read(4))[0]
            _host_os = reader.read(1)[0]
            file_crc = struct.unpack("<I", reader.read(4))[0]
            _ftime = struct.unpack("<I", reader.read(4))[0]
            _unp_ver = reader.read(1)[0]
            method = reader.read(1)[0]
            name_size = struct.unpack("<H", reader.read(2))[0]
            _attr = struct.unpack("<I", reader.read(4))[0]

            # Initialize high pack/unp sizes
            high_pack_size = 0
            high_unp_size = 0

            # Check if high pack/unp sizes are present
            current_pos = 4 + 4 + 1 + 4 + 4 + 1 + 1 + 2 + 4
            if head_flags & FLAG_HAS_HIGH_SIZE:
                logger.debug("File has high pack/unp sizes")
                high_pack_size = struct.unpack("<I", reader.read(4))[0]
                high_unp_size = struct.unpack("<I", reader.read(4))[0]
                current_pos += 8

            # Calculate actual sizes
            full_pack_size = pack_size + (high_pack_size << 32)
            full_unp_size = unp_size + (high_unp_size << 32)

            # Handle filename reading
            remaining = len(file_header_data) - current_pos
            if remaining < name_size:
                # Need to read more data
                logger.debug(
                    f"Need to read more data for filename: {remaining}/{name_size} bytes available"
                )
                more_data = self.read_bytes(
                    position + 7 + current_pos, name_size - remaining
                )
                file_name_data = reader.read(remaining) + more_data
            else:
                file_name_data = reader.read(name_size)

            # Handle Unicode filenames
            if head_flags & FLAG_HAS_UNICODE_NAME:
                logger.debug("Processing Unicode filename")
                zero_pos = file_name_data.find(b"\x00")
                if zero_pos != -1:
                    file_name = file_name_data[:zero_pos].decode(
                        "ascii", errors="replace"
                    )
                else:
                    file_name = file_name_data.decode("utf-8", errors="replace")
            else:
                file_name = file_name_data.decode("ascii", errors="replace")

            is_directory = (head_flags & FLAG_DIRECTORY) == FLAG_DIRECTORY
            logger.debug(f"{'Directory' if is_directory else 'File'}: {file_name}")

            # Calculate positions for byte range info
            data_offset = position + head_size
            next_pos = data_offset

            # If the block has data, skip over it
            if head_flags & FLAG_HAS_DATA:
                next_pos += full_pack_size

            file_info = RarFile(
                name=file_name,
                size=full_unp_size,
                compressed_size=full_pack_size,
                method=method,
                crc=file_crc,
                is_directory=is_directory,
                data_offset=data_offset,
                next_offset=next_pos,
            )

            logger.debug(
                f"File header parsed: {file_name} (Size: {full_unp_size}, Compressed: {full_pack_size})"
            )
            return file_info, next_pos

        except Exception as e:
            logger.error(f"Error parsing file header at position {position}: {e}")
            # Return the next position as a best guess
            return (
                None,
                position + head_size if "head_size" in locals() else position + 7,
            )

    def iter_files(self) -> Generator[RarFile, None, None]:
        """Iterate through all files in the RAR3 archive.

        Yields:
            RarFile: RarFile objects in the archive one by one

        Raises:
            RarMarkerNotFoundError: If the RAR marker is not found
            InvalidRarFormatError: If the archive format is invalid
            NetworkError: If there's a network-related error
        """
        logger.debug("Finding RAR3 marker...")
        pos = self._find_rar_marker()
        logger.debug(f"RAR3 marker found at position {pos}")
        pos += len(RAR3_MARKER)  # Skip marker block

        logger.debug("Reading archive header...")
        header_data = self.read_bytes(pos, 7)
        head_type = header_data[2]
        head_size = struct.unpack("<H", header_data[5:7])[0]

        if head_type != RAR3_BLOCK_HEADER:
            logger.error("Invalid RAR3 format - archive header not found")
            raise InvalidRarFormatError("Invalid RAR3 format: archive header not found")

        pos += head_size  # Skip archive header
        logger.debug(f"Archive header processed, moving to position {pos}")

        # Process file entries
        file_count = 0
        logger.debug("Processing file entries...")
        while True:
            try:
                # Read block header
                header_data = self.read_bytes(pos, 7)
                if len(header_data) < 7:
                    logger.debug("Reached end of file (incomplete header)")
                    break

                head_type = header_data[2]
                head_flags = struct.unpack("<H", header_data[3:5])[0]
                head_size = struct.unpack("<H", header_data[5:7])[0]

                # Check if we've reached the end of archive marker
                if head_type == RAR3_BLOCK_END:
                    logger.debug("End of archive marker found")
                    break

                # Check if we have a file block
                if head_type == RAR3_BLOCK_FILE:
                    logger.debug(f"Found file entry at position {pos}")
                    file_info, pos = self._parse_file_header(pos)
                    if file_info:
                        file_count += 1
                        logger.debug(
                            f"Processed file {file_count}: {file_info.name} "
                            f"({file_info.size} bytes, {file_info.compressed_size} compressed)"
                        )
                        yield file_info
                else:
                    logger.debug(
                        f"Skipping non-file block of type {head_type} at position {pos}"
                    )
                    pos += head_size

                    # If this block has data, skip it too (without downloading)
                    if head_flags & FLAG_HAS_DATA:
                        # Read just the ADD_SIZE field
                        add_size_data = self.read_bytes(pos - 4, 4)
                        add_size = struct.unpack("<I", add_size_data)[0]
                        pos += add_size
                        logger.debug(f"Skipping additional {add_size} bytes of data")

            except Exception as e:
                logger.error(f"Error processing block: {e}")
                # Likely reached end of archive
                break

        logger.debug(
            f"Finished processing. Found {file_count} files. "
            f"Total bytes read: {self.total_read}"
        )

    def read_file(self, file_info: RarFile) -> bytes:
        """Returns the raw file data for a given RarFile object.

        Only supports non-compressed files (method 0x30 "Store").

        Args:
            file_info (RarFile): RarFile object to download

        Returns:
            bytes: Raw file data

        Raises:
            DirectoryDownloadNotSupportedError: If the file is a directory
            CompressionNotSupportedError: If the file uses compression
            NetworkError: If there's a network-related error
        """
        if file_info.is_directory:
            raise DirectoryDownloadNotSupportedError(
                f"Directory downloads are not supported: {file_info.name}"
            )

        if file_info.method != COMPRESSION_METHODS_REVERSE["Store"]:
            raise CompressionNotSupportedError(
                f"Currently only uncompressed files (method 0x30 'Store') are "
                f"supported. This file uses method {hex(file_info.method)} "
                f"({COMPRESSION_METHODS.get(file_info.method, 'Unknown')})"
            )

        logger.info(
            f"Reading file: {file_info.name} ({file_info.data_offset}-{file_info.next_offset - 1}) "
            f"({file_info.compressed_size} bytes)"
        )
        data = self.read_bytes(file_info.data_offset, file_info.compressed_size)
        return data
