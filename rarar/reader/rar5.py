import logging
from typing import Generator

from ..const import MAX_SEARCH_SIZE, RAR5_MARKER
from ..exceptions import NotImplementedError, RarMarkerNotFoundError
from ..models import RarFile
from .base import RarReaderBase

logger = logging.getLogger("rarar")


class Rar5Reader(RarReaderBase):
    """Reader for RAR 5.0 format archives."""

    def _find_rar_marker(self) -> int:
        """Find the RAR5 marker in the file using small chunk requests.

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

                marker_pos = chunk.find(RAR5_MARKER)
                if marker_pos != -1:
                    logger.debug(
                        f"RAR5 marker found at position {position + marker_pos}"
                    )
                    return position + marker_pos

                # Move forward by chunk size minus the marker length to ensure we don't miss it
                # if it spans two chunks
                position += max(1, len(chunk) - len(RAR5_MARKER) + 1)

            except Exception:
                logger.error("Error while searching for RAR5 marker", exc_info=True)
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

            # Variable length integers are imitted to 10 bytes in RAR5
            if bytes_read >= 10:
                logger.warning("Variable-length integer exceeded 10 bytes")
                break

        return result, bytes_read

    def _parse_file_header(self, position: int) -> tuple[RarFile | None, int]:
        """Parse a RAR5 file header block and return the file info and next position.

        Args:
            position (int): Starting position of the file header

        Returns:
            tuple[RarFile | None, int]: Tuple of (file_info, next_position)
        """
        logger.error("RAR5 file header parsing not implemented yet")
        return None, position

    def iter_files(self) -> Generator[RarFile, None, None]:
        """Iterate through all files in the RAR5 archive.

        Yields:
            RarFile: RarFile objects in the archive one by one
        """
        raise NotImplementedError("RAR5 support not fully implemented yet")

    def read_file(self, file_info: RarFile) -> bytes:
        """Returns the raw file data for a given RarFile object.

        Args:
            file_info (RarFile): RarFile object to read

        Returns:
            bytes: Raw file data
        """
        raise NotImplementedError("RAR5 support not fully implemented yet")
