"""Tests for unrar CLI fallback decompression."""

import io
from pathlib import Path
from types import SimpleNamespace

import pytest

from rarar.exceptions import CompressionNotSupportedError
from rarar.models import RarFile
from rarar.reader.base import RarReaderBase


class _DummyReader(RarReaderBase):
    def _find_rar_marker(self) -> int:
        return 0

    def _parse_file_header(self, position: int) -> tuple[RarFile | None, int]:
        return None, position

    def generate_files(self):
        if False:
            yield

    def read_file(self, file_info: RarFile) -> bytes:
        return b""


def _compressed_file(path: str = "nested/test.bin") -> RarFile:
    return RarFile(
        path=Path(path),
        size=3,
        compressed_size=2,
        method=0x35,
        crc=0,
        is_directory=False,
        data_offset=0,
        next_offset=2,
    )


def test_decompress_uses_local_archive_path(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    archive = tmp_path / "sample.rar"
    archive.write_bytes(b"RAR")

    captured_command: list[str] = []

    def fake_run(command: list[str], check: bool, capture_output: bool):
        captured_command.extend(command)
        assert check is False
        assert capture_output is True
        return SimpleNamespace(returncode=0, stdout=b"abc", stderr=b"")

    monkeypatch.setattr("rarar.reader.base.shutil.which", lambda _: "/usr/bin/unrar")
    monkeypatch.setattr("rarar.reader.base.subprocess.run", fake_run)

    reader = _DummyReader(str(archive))
    output = reader._decompress_file(_compressed_file())

    assert output == b"abc"
    assert captured_command[0] == "/usr/bin/unrar"
    assert captured_command[5] == str(archive)
    assert captured_command[6] == "nested/test.bin"


def test_decompress_materializes_file_like_source(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = io.BytesIO(b"RAR-DATA")
    archive_paths: list[str] = []

    def fake_run(command: list[str], check: bool, capture_output: bool):
        archive_path = Path(command[5])
        archive_paths.append(str(archive_path))
        assert archive_path.is_file()
        assert archive_path.read_bytes() == b"RAR-DATA"
        return SimpleNamespace(returncode=0, stdout=b"xyz", stderr=b"")

    monkeypatch.setattr("rarar.reader.base.shutil.which", lambda _: "/usr/bin/unrar")
    monkeypatch.setattr("rarar.reader.base.subprocess.run", fake_run)

    reader = _DummyReader(source)
    first = reader._decompress_file(_compressed_file("a.bin"))
    second = reader._decompress_file(_compressed_file("b.bin"))

    assert first == b"xyz"
    assert second == b"xyz"
    assert len(archive_paths) == 2
    assert archive_paths[0] == archive_paths[1]


def test_decompress_requires_unrar_binary(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("rarar.reader.base.shutil.which", lambda _: None)

    reader = _DummyReader(io.BytesIO(b"RAR"))
    with pytest.raises(CompressionNotSupportedError, match="unrar"):
        reader._decompress_file(_compressed_file())


def test_decompress_raises_for_unrar_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("rarar.reader.base.shutil.which", lambda _: "/usr/bin/unrar")

    def fake_run(command: list[str], check: bool, capture_output: bool):
        return SimpleNamespace(returncode=10, stdout=b"", stderr=b"wrong password")

    monkeypatch.setattr("rarar.reader.base.subprocess.run", fake_run)

    reader = _DummyReader(io.BytesIO(b"RAR"))
    with pytest.raises(CompressionNotSupportedError, match="wrong password"):
        reader._decompress_file(_compressed_file())


def test_decompress_uses_password_switch(monkeypatch: pytest.MonkeyPatch) -> None:
    captured_command: list[str] = []

    def fake_run(command: list[str], check: bool, capture_output: bool):
        captured_command.extend(command)
        return SimpleNamespace(returncode=0, stdout=b"abc", stderr=b"")

    monkeypatch.setattr("rarar.reader.base.shutil.which", lambda _: "/usr/bin/unrar")
    monkeypatch.setattr("rarar.reader.base.subprocess.run", fake_run)

    reader = _DummyReader(io.BytesIO(b"RAR"), password="secret")
    output = reader._decompress_file(_compressed_file())

    assert output == b"abc"
    assert "-psecret" in captured_command
