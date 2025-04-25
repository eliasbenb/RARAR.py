import logging

import httpx

from ..exceptions import NetworkError, RangeRequestsNotSupportedError

logger = logging.getLogger("rarar")


class HttpFile:
    """Class for handling HTTP file operations with range requests."""

    def __init__(self, url: str, session: httpx.Client | None = None):
        self.url = url
        self.session = session or httpx.Client(http2=False)
        self.position = 0
        self.total_downloaded = 0

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

        end = self.position + size - 1
        headers = {"Range": f"bytes={self.position}-{end}"}

        logger.debug(f"Requesting bytes {self.position}-{end} ({size} bytes)")

        try:
            response = self.session.get(self.url, headers=headers)

            # Check if range requests are supported
            if response.status_code == 200 and "Content-Range" not in response.headers:
                raise RangeRequestsNotSupportedError(
                    "The server does not support HTTP range requests"
                )

            if response.status_code not in (200, 206):
                raise NetworkError(
                    f"Failed to read bytes from URL: {response.status_code}"
                )

            content = response.content
            self.total_downloaded += len(content)
            self.position += len(content)

            logger.debug(f"Total downloaded so far: {self.total_downloaded} bytes")

            if len(content) != size and response.status_code == 206:
                logger.warning(f"Expected {size} bytes but got {len(content)} bytes")

            return content

        except httpx.RequestError as e:
            raise NetworkError(f"HTTP request failed: {str(e)}")
