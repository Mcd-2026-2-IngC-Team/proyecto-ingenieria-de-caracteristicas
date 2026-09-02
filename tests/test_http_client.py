from contextlib import contextmanager

import httpx2

from project_name.clients.http import HttpClient
from project_name.policies.file import FilePolicy, OnExists


class FakeResponse:
    def __init__(self, chunks):
        self._chunks = chunks

    def raise_for_status(self):
        pass

    def iter_bytes(self):
        yield from self._chunks


def fake_stream_factory(chunks, calls):
    @contextmanager
    def fake_stream(method, url, **kwargs):
        calls.append({"method": method, "url": url, **kwargs})
        yield FakeResponse(chunks)

    return fake_stream


def test_download_skips_when_policy_says_no(tmp_path, monkeypatch):
    calls = []
    monkeypatch.setattr(httpx2, "stream", fake_stream_factory([b"data"], calls))

    destination = tmp_path / "already-there.zip"
    destination.write_bytes(b"old")

    client = HttpClient(file_policy=FilePolicy(on_exists=OnExists.SKIP))
    client.download(url="https://example.com/file.zip", destination=destination)

    assert calls == []
    assert destination.read_bytes() == b"old"


def test_download_streams_response_to_destination(tmp_path, monkeypatch):
    calls = []
    monkeypatch.setattr(httpx2, "stream", fake_stream_factory([b"hello ", b"world"], calls))

    destination = tmp_path / "nested" / "file.zip"

    client = HttpClient(file_policy=FilePolicy(on_exists=OnExists.SKIP))
    client.download(url="https://example.com/file.zip", destination=destination)

    assert destination.read_bytes() == b"hello world"
    assert calls == [
        {"method": "GET", "url": "https://example.com/file.zip", "follow_redirects": True}
    ]
