from dataclasses import dataclass
from typing import Any

from .const import COMPRESSION_METHODS


@dataclass
class RarFile:
    name: str
    size: int
    compressed_size: int
    method: int
    crc: int
    is_directory: bool
    data_offset: int
    next_offset: int

    def __str__(self) -> str:
        """User-friendly string representation of the file."""
        file_type = "Directory" if self.is_directory else "File"
        method_name = COMPRESSION_METHODS.get(
            self.method, f"Unknown ({hex(self.method)})"
        )

        byte_range = (
            f", Bytes Range: {self.data_offset}-{self.next_offset - 1}"
            if not self.is_directory
            else ""
        )

        return (
            f"{file_type}: {self.name} (Size: {self.size:,} bytes, Compressed: {self.compressed_size:,} bytes, "
            + f"Method: {method_name}{byte_range})"
        )

    def to_dict(self) -> dict[str, Any]:
        """Convert to a dictionary for JSON serialization.

        Returns:
            dict[str, Any]: Dictionary representation of the RarFile object
        """
        return {
            "name": self.name,
            "size": self.size,
            "compressed_size": self.compressed_size,
            "method": self.method,
            "method_name": COMPRESSION_METHODS.get(
                self.method, f"Unknown ({hex(self.method)})"
            ),
            "crc": self.crc,
            "is_directory": self.is_directory,
            "data_range": [self.data_offset, self.next_offset - 1]
            if not self.is_directory
            else None,
        }
