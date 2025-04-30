import logging

import httpx

from ..exceptions import NetworkError

logger = logging.getLogger("rarar")


class HttpFile:
    """Class for handling HTTP file operations with range requests."""

    def __init__(self, url: str, session: httpx.Client | None = None):
        self.url = url
        self.session = session or httpx.Client(http2=True, follow_redirects=True)
        self.position = 0
        self.total_downloaded = 0
        self.file_size = self._get_file_size()

    def _get_file_size(self) -> int | None:
        """Get the total file size from the server."""
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

        end = self.position + size - 1
        headers = {"Range": f"bytes={self.position}-{end}"}

        logger.debug(f"Requesting bytes {self.position}-{end} ({size} bytes)")

        try:
            response = self.session.get(self.url, headers=headers)

            # Handle successful partial content
            if response.status_code == 206:
                content = response.content
                self.total_downloaded += len(content)
                self.position += len(content)
                return content

            # Handle full content (some servers return 200 for Range requests)
            elif response.status_code == 200:
                content = response.content[self.position : self.position + size]
                self.total_downloaded += len(content)
                self.position += len(content)
                return content

            # Handle range not satisfiable (416) - we're at EOF
            elif response.status_code == 416:
                return b""

            else:
                raise NetworkError(f"Failed to read bytes: {response.status_code}")

        except httpx.RequestError as e:
            if "peer closed connection" in str(e).lower():
                return b""
            raise NetworkError(f"HTTP request failed: {str(e)}")

    def close(self) -> None:
        """Close the HTTP session."""
        if self.session:
            self.session.close()
        self.position = 0
