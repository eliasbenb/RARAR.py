"""Tests for reader factory behavior."""

import io
from pathlib import Path

import pytest

from rarar.const import RAR3_MARKER, RAR5_MARKER
from rarar.exceptions import UnsupportedRarVersionError
from rarar.reader import factory
from rarar.reader.factory import RarReader
from rarar.reader.multipart_file import MultipartFile


class _DummyReader:
    def __init__(
        self,
        source: str | io.BytesIO,
        chunk_size: int,
        session: object,
        password: str | None = None,
    ) -> None:
        self.source = source
        self.chunk_size = chunk_size
        self.session = session
        self.password = password


def test_force_version_4_uses_rar3_reader(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(factory, "Rar3Reader", _DummyReader)

    reader = RarReader(io.BytesIO(RAR3_MARKER), force_version=4)

    assert isinstance(reader, _DummyReader)


def test_force_version_5_uses_rar5_reader(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(factory, "Rar5Reader", _DummyReader)

    reader = RarReader(io.BytesIO(RAR5_MARKER), force_version=5)

    assert isinstance(reader, _DummyReader)


def test_invalid_force_version_raises() -> None:
    with pytest.raises(UnsupportedRarVersionError):
        RarReader(io.BytesIO(RAR5_MARKER), force_version=99)


def test_detects_rar3_marker(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(factory, "Rar3Reader", _DummyReader)

    data = b"x" * 32 + RAR3_MARKER + b"more"
    reader = RarReader(io.BytesIO(data))

    assert isinstance(reader, _DummyReader)


def test_detects_rar5_marker(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(factory, "Rar5Reader", _DummyReader)

    data = b"x" * 32 + RAR5_MARKER + b"more"
    reader = RarReader(io.BytesIO(data))

    assert isinstance(reader, _DummyReader)


def test_local_part_archive_uses_multipart_source(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(factory, "Rar3Reader", _DummyReader)

    first = tmp_path / "set.part1.rar"
    second = tmp_path / "set.part2.rar"
    first.write_bytes(RAR3_MARKER + b"abc")
    second.write_bytes(b"def")

    reader = RarReader(str(first))

    assert isinstance(reader, _DummyReader)
    assert isinstance(reader.source, MultipartFile)


def test_password_is_forwarded_to_reader(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(factory, "Rar5Reader", _DummyReader)

    reader = RarReader(io.BytesIO(RAR5_MARKER), force_version=5, password="secret")

    assert isinstance(reader, _DummyReader)
    assert reader.password == "secret"
