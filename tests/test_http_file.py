"""Tests for HTTP file handler caching behavior."""

from rarar.reader.http_file import HttpFile


class _FakeResponse:
    def __init__(
        self,
        status_code: int,
        content: bytes = b"",
        headers: dict[str, str] | None = None,
    ):
        self.status_code = status_code
        self.content = content
        self.headers = headers or {}


class _FakeSession:
    def __init__(self, payload: bytes):
        self.payload = payload
        self.get_calls = 0
        self.closed = False

    def head(self, url: str) -> _FakeResponse:
        return _FakeResponse(200, headers={"Content-Length": str(len(self.payload))})

    def get(self, url: str, headers: dict[str, str]) -> _FakeResponse:
        self.get_calls += 1
        range_value = headers["Range"]
        start_end = range_value.removeprefix("bytes=")
        start_str, end_str = start_end.split("-")
        start, end = int(start_str), int(end_str)

        if start >= len(self.payload):
            return _FakeResponse(416)

        end = min(end, len(self.payload) - 1)
        return _FakeResponse(206, content=self.payload[start : end + 1])

    def close(self) -> None:
        self.closed = True


def test_http_file_read_ahead_cache_handles_sequential_reads() -> None:
    payload = bytes(range(256)) * 2048
    session = _FakeSession(payload)

    http_file = HttpFile("https://example.invalid/file.rar", session=session)

    first = http_file.read(1024)
    second = http_file.read(1024)

    assert first == payload[:1024]
    assert second == payload[1024:2048]
    assert session.get_calls == 1


def test_http_file_cache_serves_back_seek_without_extra_request() -> None:
    payload = bytes(range(256)) * 2048
    session = _FakeSession(payload)

    http_file = HttpFile("https://example.invalid/file.rar", session=session)

    _ = http_file.read(4096)
    assert session.get_calls == 1

    http_file.seek(512)
    cached = http_file.read(256)

    assert cached == payload[512:768]
    assert session.get_calls == 1
