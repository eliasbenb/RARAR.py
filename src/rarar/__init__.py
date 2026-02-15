"""RARAR package."""

from importlib.metadata import PackageNotFoundError, version

from rarar.models import RarFile
from rarar.reader.factory import RarReader

__author__ = "Elias Benbourenane <eliasbenbourenane@gmail.com>"
__credits__ = ["eliasbenb"]
__license__ = "MIT"
__maintainer__ = "eliasbenb"
__email__ = "eliasbenbourenane@gmail.com"
try:
    __version__ = version("rarar")
except PackageNotFoundError:
    __version__ = "0.0.0"


import logging

logging.getLogger("rarar").addHandler(logging.NullHandler())
logging.getLogger("httpx").setLevel(logging.WARNING)


__all__ = ["RarFile", "RarReader"]
