class RaRarError(Exception):
    """Base exception for all RARAR errors."""

    pass


class UnknownSourceTypeError(RaRarError):
    """Exception raised when the source's type is unknown or unsupported."""

    pass


class RarMarkerNotFoundError(RaRarError):
    """Exception raised when the RAR marker is not found in the file."""

    pass


class InvalidRarFormatError(RaRarError):
    """Exception raised when the file does not follow the expected RAR format."""

    pass


class UnsupportedRarVersionError(RaRarError):
    """Exception raised when the RAR version is not supported."""

    pass


class NetworkError(RaRarError):
    """Exception raised when there's an issue with network requests."""

    pass


class RangeRequestsNotSupportedError(NetworkError):
    """Exception raised when the server does not support HTTP Range requests."""

    pass


class FileExtractionError(RaRarError):
    """Exception raised when there's an issue extracting a file from the archive."""

    pass


class CompressionNotSupportedError(RaRarError):
    """Exception raised when trying to extract a file with unsupported compression method."""

    pass


class DirectoryDownloadNotSupportedError(RaRarError):
    """Exception raised when trying to download a directory from a remote source."""

    pass


class NotImplementedError(RaRarError):
    """Exception raised when a feature is not yet implemented."""

    pass
