import io
import logging
import pathlib
from abc import ABC, abstractmethod
from pathlib import Path
from typing import BinaryIO, Generator
from urllib.parse import urlsplit

import requests

from ..const import DEFAULT_CHUNK_SIZE
from ..exceptions import UnknownSourceTypeError
from ..models import RarFile
from .http_file import HttpFile

logger = logging.getLogger("rarar")


class RarReaderBase(ABC):
    """Abstract base class for RAR format readers."""

    def __init__(
        self,
        source: str | BinaryIO,
        chunk_size: int = DEFAULT_CHUNK_SIZE,
        session: requests.Session | None = None,
    ) -> None:
        """Initialize the RAR reader with a source.

        Args:
            source (str | BinaryIO): Either a file-like object with seek and read methods,
                                    a URL, or a local file path
            chunk_size (int): Size of chunks to read when searching
            session (requests.Session | None): Session to use for HTTP requests if source is a URL

        Raises:
            UnknownSourceTypeError: If the source type is not recognized
        """
        if isinstance(source, (io.BufferedIOBase, io.RawIOBase)):
            self.file_obj = source
        elif isinstance(source, str) and self._is_url(source):
            self.file_obj = HttpFile(source, session)
        elif isinstance(source, str) and pathlib.Path(source).is_file():
            self.file_obj = open(source, "rb")
        else:
            raise UnknownSourceTypeError(f"Unknown source type: {type(source)}")

        self.chunk_size = chunk_size
        self.total_read = 0

    @staticmethod
    def _is_url(source: str) -> bool:
        """Check if the source is a URL.

        Args:
            source (str): The source to check

        Returns:
            bool: True if the source is a URL, False otherwise
        """
        try:
            result = urlsplit(source)
            return bool(result.scheme and result.netloc)
        except ValueError:
            return False

    def read_bytes(self, start: int, length: int) -> bytes:
        """Read a range of bytes from the file-like object.

        Args:
            start (int): Starting byte position
            length (int): Number of bytes to read

        Returns:
            bytes: The requested bytes
        """
        if length <= 0:
            return b""

        self.file_obj.seek(start)
        data = self.file_obj.read(length)
        self.total_read += len(data)
        logger.debug(f"Read {len(data)} bytes from position {start}")

        return data

    @abstractmethod
    def _find_rar_marker(self) -> int:
        """Find the RAR marker in the file.

        Returns:
            int: Position of the RAR marker in the file

        Raises:
            RarMarkerNotFoundError: If the RAR marker is not found
        """
        pass

    @abstractmethod
    def _parse_file_header(self, position: int) -> tuple[RarFile | None, int]:
        """Parse a file header block and return the file info and next position.

        Args:
            position (int): Starting position of the file header

        Returns:
            tuple[RarFile | None, int]: Tuple of (file_info, next_position)
        """
        pass

    @abstractmethod
    def iter_files(self) -> Generator[RarFile, None, None]:
        """Iterate through all files in the RAR archive.

        Yields:
            RarFile: RarFile objects in the archive one by one

        Raises:
            RarMarkerNotFoundError: If the RAR marker is not found
            InvalidRarFormatError: If the archive format is invalid
            NetworkError: If there's a network-related error
        """
        pass

    @abstractmethod
    def read_file(self, file_info: RarFile) -> bytes:
        """Returns the raw file data for a given RarFile object.

        Args:
            file_info (RarFile): RarFile object to read

        Returns:
            bytes: Raw file data

        Raises:
            DirectoryExtractNotSupportedError: If the file is a directory
            CompressionNotSupportedError: If the file uses compression
            NetworkError: If there's a network-related error
        """
        pass

    def list_files(self) -> list[RarFile]:
        """List all files in the RAR archive.

        Returns:
            list[RarFile]: List of RarFile objects in the archive
        """
        return list(self.iter_files())

    def extract_file(
        self, file_info: RarFile, output_path: str | Path | None = None
    ) -> bool:
        """Extracts a file from the RAR archive.

        Only supports non-compressed files (method 0x30 "Store").

        Args:
            file_info (RarFile): RarFile object to extract
            output_path (str | Path | None): Path to save the extracted file. If None, uses the file name from the archive.

        Returns:
            bool: True if the file was extracted successfully, False otherwise
        """
        if not output_path:
            output_path = file_info.path
        else:
            output_path = Path(output_path)

        try:
            output_path.parent.mkdir(parents=True, exist_ok=True)
            data = self.read_file(file_info)
            with output_path.open("wb") as f:
                f.write(data)
            logger.info(f"File extracted successfully: {output_path}")
            return True
        except Exception:
            logger.error(f"Error extracting file: {file_info.path}", exc_info=True)
            return False
