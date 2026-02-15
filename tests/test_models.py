"""Tests for data models."""

from pathlib import Path

from rarar.models import RarFile


def _make_file(**overrides: object) -> RarFile:
    defaults: dict[str, object] = {
        "path": Path("folder/file.txt"),
        "size": 1536,
        "compressed_size": 1536,
        "method": 0x30,
        "crc": 12345,
        "is_directory": False,
        "data_offset": 100,
        "next_offset": 1636,
    }
    defaults.update(overrides)
    return RarFile(**defaults)


def test_rar_file_name_and_human_size() -> None:
    rar_file = _make_file()

    assert rar_file.name == "file.txt"
    assert rar_file.human_size == "1.50 KB"


def test_rar_file_to_dict_for_regular_file() -> None:
    rar_file = _make_file()

    result = rar_file.to_dict()

    assert result["path"] == "folder/file.txt"
    assert result["method_name"] == "Store"
    assert result["data_range"] == [100, 1635]


def test_rar_file_to_dict_for_directory() -> None:
    rar_dir = _make_file(path=Path("folder"), is_directory=True)

    result = rar_dir.to_dict()

    assert result["is_directory"] is True
    assert result["data_range"] is None
