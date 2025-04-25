from .models import RarFile
from .reader.factory import RarReader

__author__ = "Elias Benbourenane <eliasbenbourenane@gmail.com>"
__credits__ = ["eliasbenb"]
__license__ = "MIT"
__maintainer__ = "eliasbenb"
__email__ = "eliasbenbourenane@gmail.com"
__version__ = "0.1.0"


import logging

logging.getLogger("rarar").addHandler(logging.NullHandler())
logging.getLogger("httpx").setLevel(logging.INFO)


__all__ = ["RarReader", "RarFile"]
