import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .const import COMPRESSION_METHODS


@dataclass
class RarFile:
    path: Path
    size: int
    compressed_size: int
    method: int
    crc: int
    is_directory: bool
    data_offset: int
    next_offset: int

    @property
    def name(self) -> str:
        """Get the name of the file or directory."""
        return self.path.name

    @property
    def human_size(self) -> str:
        """Convert a size in bytes to a human-readable string

        Returns:
            str: Human-readable size string
        """
        size = self.size
        for unit in ["B", "KB", "MB", "GB", "TB"]:
            if size < 1024:
                return f"{size:,.2f} {unit}"
            size /= 1024
        return f"{size:,.2f} PB"

    def __str__(self) -> str:
        """User-friendly string representation of the file."""
        if self.is_directory:
            return f"{self.path}{os.sep}"
        return (
            f"{self.path} ({self.human_size}) "
            f"(Bytes: {self.data_offset}-{self.next_offset - 1})"
        )

    def to_dict(self) -> dict[str, Any]:
        """Convert to a dictionary for JSON serialization.

        Returns:
            dict[str, Any]: Dictionary representation of the RarFile object
        """
        return {
            "path": self.path.as_posix(),
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
