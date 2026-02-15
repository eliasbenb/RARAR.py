"""Tests for RAR5 reader parsing path."""

import io

from rarar.const import (
    RAR5_BLOCK_END,
    RAR5_BLOCK_FILE,
    RAR5_BLOCK_FLAG_DATA_AREA,
    RAR5_FILE_FLAG_HAS_CRC32,
    RAR5_MARKER,
)
from rarar.reader.rar5 import Rar5Reader


def _vint(value: int) -> bytes:
    parts = bytearray()
    current = value
    while True:
        byte = current & 0x7F
        current >>= 7
        if current:
            parts.append(byte | 0x80)
        else:
            parts.append(byte)
            return bytes(parts)


def test_rar5_generate_files_parses_single_file_block() -> None:
    name = b"file.bin"
    file_data = b"HELLO"
    file_crc = 0x12345678

    file_body = b"".join(
        [
            _vint(RAR5_BLOCK_FILE),
            _vint(RAR5_BLOCK_FLAG_DATA_AREA),
            _vint(len(file_data)),
            _vint(RAR5_FILE_FLAG_HAS_CRC32),
            _vint(len(file_data)),
            _vint(0),
            file_crc.to_bytes(4, "little"),
            _vint(0),
            _vint(1),
            _vint(len(name)),
            name,
        ]
    )
    file_block = b"".join(
        [
            (0).to_bytes(4, "little"),
            _vint(len(file_body)),
            file_body,
            file_data,
        ]
    )

    end_body = b"".join([_vint(RAR5_BLOCK_END), _vint(0)])
    end_block = b"".join([(0).to_bytes(4, "little"), _vint(len(end_body)), end_body])

    archive = RAR5_MARKER + file_block + end_block

    reader = Rar5Reader(io.BytesIO(archive))
    files = list(reader)

    assert len(files) == 1
    parsed = files[0]
    assert parsed.path.as_posix() == "file.bin"
    assert parsed.size == len(file_data)
    assert parsed.compressed_size == len(file_data)
    assert parsed.crc == file_crc
    assert reader.read_file(parsed) == file_data
