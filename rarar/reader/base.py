import io
import logging
import pathlib
from abc import ABC, abstractmethod
from pathlib import Path
from typing import BinaryIO, Generator, Iterator, Self
from urllib.parse import urlsplit

import httpx

from ..const import DEFAULT_CHUNK_SIZE
from ..exceptions import DirectoryExtractNotSupportedError, UnknownSourceTypeError
from ..models import RarFile
from .http_file import HttpFile

logger = logging.getLogger("rarar")


class RarReaderBase(ABC, Iterator[RarFile]):
    """Abstract base class for RAR format readers."""

    RAR_MARKER_SIG: bytes = b"\x99\xaa\xbb\xcc\xdd\xee\xff"

    def __init__(
        self,
        source: str | BinaryIO,
        chunk_size: int = DEFAULT_CHUNK_SIZE,
        session: httpx.Client | None = None,
    ) -> None:
        """Initialize the RAR reader with a source.

        Args:
            source (str | BinaryIO): Either a file-like object with seek and read methods, a URL, or a local file path
            chunk_size (int): Size of chunks to read when searching
            session (httpx.Client | None): Session to use for HTTP requests if source is a URL

        Raises:
            UnknownSourceTypeError: If the source type is not recognized
        """
        if isinstance(source, io.IOBase):
            self.file_obj = source
        elif isinstance(source, str) and self._is_url(source):
            self.file_obj = HttpFile(source, session)
        elif isinstance(source, str) and pathlib.Path(source).is_file():
            self.file_obj = open(source, "rb")
        else:
            raise UnknownSourceTypeError(f"Unknown source type: {type(source)}")

        self.chunk_size = chunk_size
        self.total_read = 0
        self._rar_marker = self._find_rar_marker()
        self._file_generator = self.generate_files()

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

        # If we got less data than expected, it might be EOF
        if len(data) < length:
            logger.debug(
                f"Partial read: requested {length} bytes, got {len(data)} bytes"
            )

        self.total_read += len(data)

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
    def generate_files(self) -> Generator[RarFile, None, None]:
        """Generate RarFile objects for each file in the archive.

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

    def _extract_file(self, file_info: RarFile, output_path: Path) -> bool:
        """Extracts a file from the RAR archive.

        Args:
            file_info (RarFile): RarFile object to extract
            output_path (Path): Path to save the extracted file

        Returns:
            bool: True if the file was extracted successfully, False otherwise
        """
        try:
            if file_info.is_directory:
                raise DirectoryExtractNotSupportedError(
                    "Extraction of directories is not supported"
                )
            data = self.read_file(file_info)
            with output_path.open("wb") as f:
                f.write(data)
            logger.info(f"File extracted successfully: {output_path}")
            return True
        except Exception:
            logger.error(f"Error extracting file: {file_info.path}", exc_info=True)
            return False

    def _extract_all(self, output_path: Path) -> bool:
        """Extracts all files in the RAR archive.

        Args:
            output_path (Path): Path to save the extracted directory

        Returns:
            bool: True if the all files were extracted successfully, False otherwise
        """
        for rar_file in self:
            if rar_file.is_directory:
                continue
            output_path = output_path / rar_file.path
            output_path.parent.mkdir(parents=True, exist_ok=True)
            if self._extract_file(rar_file, output_path) is False:
                return False
        return True

    def extract(
        self, file_info: RarFile | None, output_path: str | Path | None = None
    ) -> bool:
        """Extract file(s) from the RAR archive.

        Only supports non-compressed files (method 0x30 "Store").

        Args:
            file_info (RarFile | None): RarFile object to extract. If None, extracts all files.
            output_path (str | Path | None): Path to save the extracted file. If None, uses the file name from the archive.

        Returns:
            bool: True if the file was extracted successfully, False otherwise
        """
        if output_path:
            output_path = Path(output_path)
        elif file_info:
            output_path = file_info.path
        else:
            output_path = Path(".")

        if not file_info:
            return self._extract_all(output_path)
        else:
            return self._extract_file(file_info, output_path)

    def _decompress_file(self, file_info: RarFile) -> bytes:
        """Decompress a file from the RAR archive.

        Args:
            file_info (RarFile): RarFile object to decompress

        Returns:
            bytes: Decompressed file data

        Raises:
            CompressionNotSupportedError: If the file uses compression
        """
        raise NotImplementedError("Decompression is a WIP")

    def __iter__(self) -> Self:
        """Return self as an iterator.

        This allows for direct iteration over the reader object.

        Returns:
            Self: Self as an iterator
        """
        self._file_generator = self.generate_files()
        return self

    def __next__(self) -> RarFile:
        """Get the next file from the RAR archive.

        Returns:
            RarFile: The next RarFile object in the archive

        Raises:
            StopIteration: When there are no more files
        """
        return next(self._file_generator)
