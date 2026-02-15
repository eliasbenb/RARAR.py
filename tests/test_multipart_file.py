"""Tests for multipart local archive support."""

from pathlib import Path

from rarar.reader.multipart_file import MultipartFile, discover_multipart_paths


def test_discover_part_style_volumes(tmp_path: Path) -> None:
    first = tmp_path / "archive.part1.rar"
    second = tmp_path / "archive.part2.rar"
    third = tmp_path / "archive.part3.rar"

    first.write_bytes(b"a")
    second.write_bytes(b"b")
    third.write_bytes(b"c")

    assert discover_multipart_paths(first) == [first, second, third]


def test_discover_legacy_volumes(tmp_path: Path) -> None:
    first = tmp_path / "archive.rar"
    second = tmp_path / "archive.r00"
    third = tmp_path / "archive.r01"

    first.write_bytes(b"a")
    second.write_bytes(b"b")
    third.write_bytes(b"c")

    assert discover_multipart_paths(first) == [first, second, third]


def test_multipart_file_reads_across_boundaries(tmp_path: Path) -> None:
    part1 = tmp_path / "data.part1.rar"
    part2 = tmp_path / "data.part2.rar"

    part1.write_bytes(b"hello")
    part2.write_bytes(b"-world")

    file_obj = MultipartFile([part1, part2])

    assert file_obj.read(8) == b"hello-wo"
    assert file_obj.tell() == 8
    assert file_obj.read(3) == b"rld"

    file_obj.seek(3)
    assert file_obj.read(5) == b"lo-wo"
    file_obj.close()
