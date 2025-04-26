import io
import logging
import pathlib
from typing import BinaryIO

import httpx

from ..const import (
    DEFAULT_CHUNK_SIZE,
    HTTP_CHUNK_SIZE,
    MAX_SEARCH_SIZE,
    RAR3_MARKER,
    RAR5_MARKER,
)
from ..exceptions import (
    RarMarkerNotFoundError,
    UnknownSourceTypeError,
    UnsupportedRarVersionError,
)
from .base import RarReaderBase
from .http_file import HttpFile
from .rar3 import Rar3Reader
from .rar5 import Rar5Reader

logger = logging.getLogger("rarar")


class RarReader:
    """Factory class to create the appropriate RAR reader based on the format."""

    def __new__(
        cls,
        source: str | BinaryIO,
        chunk_size: int | None = None,
        session: httpx.Client | None = None,
        force_version: int | None = None,
    ) -> RarReaderBase:
        """Create the appropriate RAR reader instance.

        Args:
            source (str | BinaryIO): The source to read from
            chunk_size (int | None): Size of chunks to read
            session (httpx.Client | None): Session for HTTP requests
            force_version (int | None): Force a specific RAR version (4 or 5)

        Returns:
            RarReaderBase: Either a Rar3Reader or Rar5Reader instance

        Raises:
            UnsupportedRarVersionError: If the RAR version is not supported
            RarMarkerNotFoundError: If no RAR marker is found
        """
        if chunk_size is None:
            if isinstance(source, str) and RarReaderBase._is_url(source):
                chunk_size = HTTP_CHUNK_SIZE
            else:
                chunk_size = DEFAULT_CHUNK_SIZE

        if force_version is not None:
            if force_version in (3, 4):
                return Rar3Reader(source, chunk_size, session)
            elif force_version == 5:
                return Rar5Reader(source, chunk_size, session)
            else:
                raise UnsupportedRarVersionError(
                    f"Unsupported RAR version: {force_version}"
                )

        # Try to detect the RAR version
        file_obj = None
        need_to_close = False
        try:
            if isinstance(source, (io.BufferedIOBase, io.RawIOBase)):
                file_obj = source
                can_reset = hasattr(file_obj, "seek")
                need_to_close = False
            elif isinstance(source, str) and RarReaderBase._is_url(source):
                file_obj = HttpFile(source, session)
                can_reset = True
                need_to_close = True
            elif isinstance(source, str) and pathlib.Path(source).is_file():
                file_obj = open(source, "rb")
                can_reset = True
                need_to_close = True
            else:
                raise UnknownSourceTypeError(f"Unknown source type: {type(source)}")

            position = 0
            max_search = MAX_SEARCH_SIZE
            version = None

            logger.debug(f"Detecting RAR version in first {max_search} bytes")
            while position < max_search:
                try:
                    file_obj.seek(position)
                    chunk = file_obj.read(min(chunk_size, max_search - position))
                    if not chunk:
                        break

                    # Check for RAR3 marker
                    marker_pos = chunk.find(RAR3_MARKER)
                    if marker_pos != -1:
                        if can_reset:
                            file_obj.seek(0)
                        version = 4
                        break

                    # Check for RAR5 marker
                    marker_pos = chunk.find(RAR5_MARKER)
                    if marker_pos != -1:
                        if can_reset:
                            file_obj.seek(0)
                        version = 5
                        break

                    # Move forward by chunk size minus the longer marker length
                    position += max(1, len(chunk) - len(RAR5_MARKER) + 1)

                except Exception as e:
                    logger.error(f"Error detecting RAR version: {e}")
                    raise

            if version is None:
                raise RarMarkerNotFoundError("No RAR marker found within search limit")

            if version in (3, 4):
                return Rar3Reader(source, chunk_size, session)
            elif version == 5:
                return Rar5Reader(source, chunk_size, session)
            else:
                raise UnsupportedRarVersionError(f"Unsupported RAR version: {version}")

        finally:
            # Clean up resources if needed
            if (
                need_to_close
                and file_obj is not None
                and isinstance(file_obj, io.IOBase)
                and not file_obj.closed
            ):
                file_obj.close()
