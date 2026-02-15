"""HTTP file handler."""

import logging
from typing import Protocol

import httpx

from rarar.exceptions import NetworkError

logger = logging.getLogger("rarar")


class HttpSession(Protocol):
    """Protocol for HTTP clients used by HttpFile."""

    def head(self, url: str):
        """Perform an HTTP HEAD request."""

    def get(self, url: str, headers: dict[str, str]):
        """Perform an HTTP GET request."""

    def close(self) -> None:
        """Close the HTTP client and release resources."""


class HttpFile:
    """Class for handling HTTP file operations with range requests."""

    def __init__(self, url: str, session: HttpSession | None = None):
        """Initialize the HttpFile with a URL."""
        self.url = url
        self.session = session or httpx.Client(http2=True, follow_redirects=True)
        self.position = 0
        self.total_downloaded = 0
        self._cache_start = 0
        self._cache_data = b""
        self._read_ahead = 256 * 1024
        self.file_size = self._get_file_size()

    def _get_file_size(self) -> int | None:
        """Get the total file size from the server.

        Returns:
            int | None: The total file size in bytes, or None if not available
        """
        try:
            response = self.session.head(self.url)
            if response.status_code == 200:
                return int(response.headers.get("Content-Length", 0))
        except Exception:
            pass
        return None

    def tell(self) -> int:
        """Get the current position in the file.

        Returns:
            int: The current position
        """
        return self.position

    def seek(self, position: int) -> int:
        """Change the current position in the file.

        Args:
            position (int): The position to seek to

        Returns:
            int: The new position after seeking
        """
        self.position = position
        return self.position

    def read(self, size: int | None = None) -> bytes:
        """Read bytes from the current position.

        Args:
            size (int | None): Number of bytes to read

        Returns:
            bytes: The requested bytes

        Raises:
            NetworkError: If the HTTP request fails
            RangeRequestsNotSupportedError: If the server doesn't support range requests
        """
        if size is None or size <= 0:
            return b""

        if self.file_size is not None:
            remaining = self.file_size - self.position
            if remaining <= 0:
                return b""
            size = min(size, remaining)

        read_start = self.position
        read_end = read_start + size

        # Serve from read-ahead cache when possible.
        cache_end = self._cache_start + len(self._cache_data)
        if (
            self._cache_data
            and self._cache_start <= read_start < cache_end
            and read_end <= cache_end
        ):
            offset = read_start - self._cache_start
            chunk = self._cache_data[offset : offset + size]
            self.position += len(chunk)
            return chunk

        request_size = max(size, self._read_ahead)
        if self.file_size is not None:
            request_size = min(request_size, self.file_size - read_start)

        end = read_start + request_size - 1
        headers = {"Range": f"bytes={read_start}-{end}"}

        logger.debug(f"Requesting bytes {self.position}-{end} ({size} bytes)")

        try:
            response = self.session.get(self.url, headers=headers)

            # Handle successful partial content
            if response.status_code == 206:
                content = response.content
                self.total_downloaded += len(content)
                self._cache_start = read_start
                self._cache_data = content

                chunk = content[:size]
                self.position += len(chunk)
                return chunk

            # Handle full content (some servers return 200 for Range requests)
            elif response.status_code == 200:
                full_content = response.content
                sliced = full_content[read_start : read_start + request_size]
                self.total_downloaded += len(full_content)
                self._cache_start = read_start
                self._cache_data = sliced

                chunk = sliced[:size]
                self.position += len(chunk)
                return chunk

            # Handle range not satisfiable (416) - we're at EOF
            elif response.status_code == 416:
                return b""

            else:
                raise NetworkError(f"Failed to read bytes: {response.status_code}")

        except httpx.RequestError as e:
            if "peer closed connection" in str(e).lower():
                return b""
            raise NetworkError(f"HTTP request failed: {e}") from e

    def close(self) -> None:
        """Close the HTTP session."""
        if self.session:
            self.session.close()
        self.position = 0
        self._cache_start = 0
        self._cache_data = b""
