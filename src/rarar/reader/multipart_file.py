"""Helpers for reading multi-part RAR archives as a single seekable stream."""

import io
import pathlib
import re
from bisect import bisect_right

_PART_STYLE_RE = re.compile(r"^(?P<base>.+)\.part(?P<number>\d+)\.rar$", re.IGNORECASE)


def discover_multipart_paths(path: pathlib.Path) -> list[pathlib.Path]:
    """Discover local RAR volume paths for supported naming schemes.

    Supported schemes:
    - ``name.part1.rar`` + ``name.part2.rar`` + ...
    - ``name.rar`` + ``name.r00`` + ``name.r01`` + ...

    Args:
        path (pathlib.Path): Path to the archive provided by the user.

    Returns:
        list[pathlib.Path]: Ordered list of volume paths. If no additional
            volumes are found, returns only the provided path.
    """
    if not path.is_file():
        return [path]

    match = _PART_STYLE_RE.match(path.name)
    if match:
        first_number = int(match.group("number"))
        if first_number != 1:
            return [path]

        base_name = match.group("base")
        number_width = len(match.group("number"))
        discovered = [path]
        volume_number = first_number + 1

        while True:
            volume_name = f"{base_name}.part{volume_number:0{number_width}d}.rar"
            volume_path = path.with_name(volume_name)
            if not volume_path.is_file():
                break
            discovered.append(volume_path)
            volume_number += 1

        return discovered

    if path.suffix.lower() == ".rar":
        discovered = [path]
        volume_number = 0
        while True:
            volume_path = path.with_suffix(f".r{volume_number:02d}")
            if not volume_path.is_file():
                break
            discovered.append(volume_path)
            volume_number += 1
        return discovered

    return [path]


class MultipartFile(io.RawIOBase):
    """Seekable read-only view over concatenated local files."""

    def __init__(self, paths: list[pathlib.Path]) -> None:
        """Initialize MultipartFile with a list of file paths.

        Args:
            paths (list[pathlib.Path]): List of file paths to concatenate. Must
                contain at least one path.
        """
        super().__init__()
        if not paths:
            raise ValueError("At least one path is required")

        self._paths = paths
        self._part_sizes = [p.stat().st_size for p in paths]
        self._part_starts = []
        offset = 0
        for part_size in self._part_sizes:
            self._part_starts.append(offset)
            offset += part_size
        self._total_size = offset

        self._position = 0
        self._open_part_index: int | None = None
        self._open_part_file: io.BufferedReader | None = None

    def readable(self) -> bool:
        """Return True, this stream supports reading."""
        return True

    def seekable(self) -> bool:
        """Return True, this stream supports seeking."""
        return True

    def tell(self) -> int:
        """Return current absolute position."""
        return self._position

    def seek(self, offset: int, whence: int = io.SEEK_SET) -> int:
        """Seek within concatenated stream."""
        if whence == io.SEEK_SET:
            new_position = offset
        elif whence == io.SEEK_CUR:
            new_position = self._position + offset
        elif whence == io.SEEK_END:
            new_position = self._total_size + offset
        else:
            raise ValueError(f"Invalid whence: {whence}")

        if new_position < 0:
            raise ValueError("Seek position cannot be negative")

        self._position = min(new_position, self._total_size)
        return self._position

    def _get_part_index_for_position(self, position: int) -> int:
        if position >= self._total_size:
            return len(self._part_starts) - 1
        return bisect_right(self._part_starts, position) - 1

    def _ensure_part_open(self, index: int) -> io.BufferedReader:
        if self._open_part_index != index or self._open_part_file is None:
            if self._open_part_file is not None:
                self._open_part_file.close()
            self._open_part_file = open(self._paths[index], "rb")  # noqa: SIM115
            self._open_part_index = index
        return self._open_part_file

    def read(self, size: int = -1) -> bytes:
        """Read bytes from concatenated stream."""
        if size == 0 or self._position >= self._total_size:
            return b""

        if size < 0:
            requested = self._total_size - self._position
        else:
            requested = min(size, self._total_size - self._position)

        remaining = requested
        chunks: list[bytes] = []

        while remaining > 0:
            part_index = self._get_part_index_for_position(self._position)
            part_start = self._part_starts[part_index]
            part_size = self._part_sizes[part_index]
            part_offset = self._position - part_start
            part_remaining = part_size - part_offset
            if part_remaining <= 0:
                break

            bytes_to_read = min(remaining, part_remaining)
            part_file = self._ensure_part_open(part_index)
            part_file.seek(part_offset)
            data = part_file.read(bytes_to_read)
            if not data:
                break

            chunks.append(data)
            read_len = len(data)
            self._position += read_len
            remaining -= read_len

        return b"".join(chunks)

    def close(self) -> None:
        """Close any open volume handle."""
        if self._open_part_file is not None:
            self._open_part_file.close()
            self._open_part_file = None
            self._open_part_index = None
        super().close()


def open_local_rar_source(path: pathlib.Path) -> io.IOBase:
    """Open local RAR source, using MultipartFile if multiple volumes exist."""
    paths = discover_multipart_paths(path)
    if len(paths) > 1:
        return MultipartFile(paths)
    return open(path, "rb")
