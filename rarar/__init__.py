from .exceptions import (
    CompressionNotSupportedError,
    FileExtractionError,
    InvalidRarFormatError,
    NetworkError,
    RangeRequestsNotSupportedError,
    RaRarError,
    RarMarkerNotFoundError,
)
from .models import RarFile
from .reader import RarReader

__author__ = "Elias Benbourenane <eliasbenbourenane@gmail.com>"
__credits__ = ["eliasbenb"]
__license__ = "MIT"
__maintainer__ = "eliasbenb"
__email__ = "eliasbenbourenane@gmail.com"
__version__ = "0.1.0"


import logging

logging.getLogger("rarar").addHandler(logging.NullHandler())


__all__ = [
    "RarReader",
    "RarFile",
    "RaRarError",
    "RarMarkerNotFoundError",
    "InvalidRarFormatError",
    "NetworkError",
    "RangeRequestsNotSupportedError",
    "FileExtractionError",
    "CompressionNotSupportedError",
]
