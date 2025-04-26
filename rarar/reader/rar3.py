import io
import logging
import struct
from pathlib import Path
from typing import Generator

from ..const import (
    MAX_SEARCH_SIZE,
    RAR3_BLOCK_END,
    RAR3_BLOCK_FILE,
    RAR3_BLOCK_HEADER,
    RAR3_COMPRESSION_METHODS,
    RAR3_COMPRESSION_METHODS_REVERSE,
    RAR3_FLAG_DIRECTORY,
    RAR3_FLAG_HAS_DATA,
    RAR3_FLAG_HAS_HIGH_SIZE,
    RAR3_FLAG_HAS_UNICODE_NAME,
    RAR3_MARKER,
)
from ..exceptions import (
    CompressionNotSupportedError,
    DirectoryExtractNotSupportedError,
    InvalidRarFormatError,
    RarMarkerNotFoundError,
)
from ..models import RarFile
from .base import RarReaderBase

logger = logging.getLogger("rarar")


class Rar3Reader(RarReaderBase):
    """Reader for RAR 3.x or 4.x format archives."""

    def _find_rar_marker(self) -> int:
        """Find the RAR3 marker in the file using small chunk requests.

        Returns:
            int: Position of the RAR marker in the file

        Raises:
            RarMarkerNotFoundError: If the RAR marker is not found
        """
        # First try to find marker in the first chunk
        first_chunk_size = 8192  # Read 8KB at once
        chunk = self.read_bytes(0, first_chunk_size)
        marker_pos = chunk.find(RAR3_MARKER)
        if marker_pos != -1:
            logger.debug(f"RAR3 marker found at position {marker_pos}")
            return marker_pos

        # If not found, continue with the original logic
        position = first_chunk_size - len(RAR3_MARKER) + 1
        max_search = MAX_SEARCH_SIZE

        logger.debug(
            f"RAR3 marker not found in first chunk, searching in first {max_search} bytes"
        )
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

    def _parse_file_header_data(
        self, header_data: bytes, position: int
    ) -> RarFile | None:
        """Parse RAR3 file header data from bytes.

        This is the core parsing logic that works with already-read header data.

        Args:
            header_data (bytes): Complete header data
            position (int): Original position in file

        Returns:
            RarFile | None: Parsed file info or None if not a file block
        """
        try:
            # Parse basic header fields
            _head_crc, head_type, head_flags = struct.unpack("<HBH", header_data[:5])
            head_size = struct.unpack("<H", header_data[5:7])[0]

            # If not a file block, return None
            if head_type != RAR3_BLOCK_FILE:
                logger.debug(f"Not a file block (type: {head_type}), skipping")
                return None

            # Use BytesIO to read from the buffer
            reader = io.BytesIO(header_data[7:])

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
            if head_flags & RAR3_FLAG_HAS_HIGH_SIZE:
                logger.debug("File has high pack/unp sizes")
                high_pack_size = struct.unpack("<I", reader.read(4))[0]
                high_unp_size = struct.unpack("<I", reader.read(4))[0]
                current_pos += 8

            # Calculate actual sizes
            full_pack_size = pack_size + (high_pack_size << 32)
            full_unp_size = unp_size + (high_unp_size << 32)

            # Handle filename reading
            file_name_data = reader.read(name_size)

            # Handle Unicode filenames
            if head_flags & RAR3_FLAG_HAS_UNICODE_NAME:
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

            is_directory = (head_flags & RAR3_FLAG_DIRECTORY) == RAR3_FLAG_DIRECTORY
            logger.debug(f"{'Directory' if is_directory else 'File'}: {file_name}")

            # Calculate positions for byte range info
            data_offset = position + head_size
            next_pos = data_offset

            # If the block has data, skip over it
            if head_flags & RAR3_FLAG_HAS_DATA:
                next_pos += full_pack_size

            file_info = RarFile(
                path=Path(file_name),
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
            return file_info

        except Exception as e:
            logger.error(f"Error parsing file header data at position {position}: {e}")
            return None

    def _parse_file_header(self, position: int) -> tuple[RarFile | None, int]:
        """Parse a RAR3 file header block and return the file info and next position.

        This method reads the header data from disk and calls the core parsing logic.

        Args:
            position (int): Starting position of the file header

        Returns:
            tuple[RarFile | None, int]: Tuple of (file_info, next_position)
        """
        logger.debug(f"Parsing RAR3 file header at position {position}")

        # Read initial chunk
        header_chunk = self.read_bytes(position, 128)

        # Get header size
        if len(header_chunk) < 7:
            return None, position

        _head_crc, head_type, _head_flags = struct.unpack("<HBH", header_chunk[:5])
        head_size = struct.unpack("<H", header_chunk[5:7])[0]

        # If not a file block, skip it
        if head_type != RAR3_BLOCK_FILE:
            logger.debug(f"Not a file block (type: {head_type}), skipping")
            return None, position + head_size

        # Check if we need more data
        if head_size > len(header_chunk):
            additional_data = self.read_bytes(
                position + len(header_chunk), head_size - len(header_chunk)
            )
            header_chunk += additional_data

        # Parse the complete header data
        file_info = self._parse_file_header_data(header_chunk[:head_size], position)

        if file_info:
            return file_info, file_info.next_offset
        else:
            return None, position + head_size

    def generate_files(self) -> Generator[RarFile, None, None]:
        """Generate RarFile objects for each file in the archive.

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

        # Read-ahead buffer
        buffer_size = 32 * 1024  # 32KB
        current_buffer = self.read_bytes(pos, buffer_size)
        buffer_offset = 0

        file_count = 0
        logger.debug("Processing file entries...")

        while True:
            # Try to read from buffer first
            if buffer_offset + 7 <= len(current_buffer):
                header_data = current_buffer[buffer_offset : buffer_offset + 7]
            else:
                # Need to refill buffer
                pos += buffer_offset
                current_buffer = self.read_bytes(pos, buffer_size)
                buffer_offset = 0
                if len(current_buffer) < 7:
                    logger.debug("Reached end of file (incomplete header)")
                    break
                header_data = current_buffer[:7]

            # Process header
            head_type = header_data[2]
            head_flags = struct.unpack("<H", header_data[3:5])[0]
            head_size = struct.unpack("<H", header_data[5:7])[0]

            if head_type == RAR3_BLOCK_END:
                logger.debug("End of archive marker found")
                break

            if head_type == RAR3_BLOCK_FILE:
                logger.debug(f"Found file entry at position {pos + buffer_offset}")
                # Parse file header from buffer if possible
                if buffer_offset + head_size <= len(current_buffer):
                    file_info = self._parse_file_header_data(
                        current_buffer[buffer_offset : buffer_offset + head_size],
                        pos + buffer_offset,
                    )
                    buffer_offset += head_size

                    # Skip file data
                    if file_info and file_info.compressed_size > 0:
                        data_size = file_info.compressed_size
                        buffer_offset += data_size
                        # If we've moved past the buffer, update position and refill
                        if buffer_offset >= len(current_buffer):
                            pos += buffer_offset
                            current_buffer = self.read_bytes(pos, buffer_size)
                            buffer_offset = 0
                else:
                    # Need direct read
                    file_info, next_pos = self._parse_file_header(pos + buffer_offset)
                    # Update buffer position to after the file data
                    if file_info:
                        buffer_offset = next_pos - pos
                    else:
                        buffer_offset += head_size

                    # If we've moved past the buffer, update position and refill
                    if buffer_offset >= len(current_buffer):
                        pos += buffer_offset
                        current_buffer = self.read_bytes(pos, buffer_size)
                        buffer_offset = 0

                if file_info:
                    file_count += 1
                    logger.debug(
                        f"Processed file {file_count}: {file_info.path} "
                        f"({file_info.size} bytes, {file_info.compressed_size} compressed)"
                    )
                    yield file_info
            else:
                logger.debug(
                    f"Skipping non-file block of type {head_type} at position {pos + buffer_offset}"
                )
                buffer_offset += head_size

                # If this block has data, skip it too
                if head_flags & RAR3_FLAG_HAS_DATA:
                    # Read just the ADD_SIZE field if it's in the buffer
                    if buffer_offset + 4 <= len(current_buffer):
                        add_size = struct.unpack(
                            "<I", current_buffer[buffer_offset - 4 : buffer_offset]
                        )[0]
                    else:
                        # Need to read directly
                        add_size_data = self.read_bytes(pos + buffer_offset - 4, 4)
                        add_size = struct.unpack("<I", add_size_data)[0]

                    buffer_offset += add_size
                    logger.debug(f"Skipping additional {add_size} bytes of data")

                    # If we've moved past the buffer, update position and refill
                    if buffer_offset >= len(current_buffer):
                        pos += buffer_offset
                        current_buffer = self.read_bytes(pos, buffer_size)
                        buffer_offset = 0

        logger.debug(
            f"Finished processing. Found {file_count} files. "
            f"Total bytes read: {self.total_read}"
        )

    def read_file(self, file_info: RarFile) -> bytes:
        """Returns the raw file data for a given RarFile object.

        Only supports non-compressed files (method 0x30 "Store").

        Args:
            file_info (RarFile): RarFile object to read

        Returns:
            bytes: Raw file data

        Raises:
            DirectoryExtractNotSupportedError: If the file is a directory
            CompressionNotSupportedError: If the file uses compression
            NetworkError: If there's a network-related error
        """
        if file_info.is_directory:
            raise DirectoryExtractNotSupportedError(
                f"Directory extracts are not supported: {file_info.path}"
            )

        if file_info.method != RAR3_COMPRESSION_METHODS_REVERSE["Store"]:
            raise CompressionNotSupportedError(
                f"Currently only uncompressed files (method 0x30 'Store') are "
                f"supported. This file uses method {hex(file_info.method)} "
                f"({RAR3_COMPRESSION_METHODS.get(file_info.method, 'Unknown')})"
            )

        logger.info(
            f"Reading file: {file_info.path} ({file_info.data_offset}-{file_info.next_offset - 1}) "
            f"({file_info.compressed_size} bytes)"
        )
        data = self.read_bytes(file_info.data_offset, file_info.compressed_size)
        return data
