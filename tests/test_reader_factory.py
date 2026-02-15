"""Tests for reader factory behavior."""

import io

import pytest

from rarar.const import RAR3_MARKER, RAR5_MARKER
from rarar.exceptions import UnsupportedRarVersionError
from rarar.reader import factory
from rarar.reader.factory import RarReader


class _DummyReader:
    def __init__(
        self, source: str | io.BytesIO, chunk_size: int, session: object
    ) -> None:
        self.source = source
        self.chunk_size = chunk_size
        self.session = session


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
