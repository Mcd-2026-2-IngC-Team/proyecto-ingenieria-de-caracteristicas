from contextlib import contextmanager
import io
import os
import zipfile

import httpx2
import pytest

from project_name.clients import http
from project_name.clients.http import DEFAULT_TIMEOUT_SECONDS, HttpClient
from project_name.policies.file import FilePolicy, OnExists


class FakeResponse:
    def __init__(self, chunks, fail_after=None):
        self._chunks = chunks
        self._fail_after = fail_after

    def raise_for_status(self):
        pass

    def iter_bytes(self):
        for index, chunk in enumerate(self._chunks):
            if index == self._fail_after:
                raise httpx2.ReadTimeout("The read operation timed out")
            yield chunk


def fake_stream_factory(chunks, calls, fail_after=None):
    @contextmanager
    def fake_stream(method, url, **kwargs):
        calls.append({"method": method, "url": url, **kwargs})
        yield FakeResponse(chunks, fail_after)

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
        {
            "method": "GET",
            "url": "https://example.com/file.zip",
            "follow_redirects": True,
            "timeout": DEFAULT_TIMEOUT_SECONDS,
        }
    ]


def test_interrupted_download_leaves_no_file_behind(tmp_path, monkeypatch):
    """Regresión: una descarga cortada no debe quedar con el nombre final, porque
    la política `skip` la daría por buena en la siguiente corrida."""
    monkeypatch.setattr(httpx2, "stream", fake_stream_factory([b"part", b"rest"], [], 1))

    destination = tmp_path / "file.zip"

    client = HttpClient(file_policy=FilePolicy(on_exists=OnExists.SKIP))
    with pytest.raises(httpx2.ReadTimeout):
        client.download(url="https://example.com/file.zip", destination=destination)

    assert list(tmp_path.iterdir()) == []


def make_nested_zip() -> tuple[bytes, bytes]:
    """ZIP 'nacional' con un ZIP por estado adentro, como los paquetes del INEGI."""
    sonora = b"sonora-" + os.urandom(64 * 1024)
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        # Miembros grandes e incompresibles, para que bajar todo se note.
        archive.writestr("01_aguascalientes.zip", os.urandom(512 * 1024))
        archive.writestr("26_sonora.zip", sonora)
        archive.writestr("32_zacatecas.zip", os.urandom(512 * 1024))
    return buffer.getvalue(), sonora


def range_server(payload: bytes, served: list[int], honor_ranges: bool = True):
    def handler(request):
        if request.method == "HEAD":
            return httpx2.Response(200, headers={"Content-Length": str(len(payload))})
        header = request.headers.get("Range")
        if not honor_ranges or header is None:
            served.append(len(payload))
            return httpx2.Response(200, content=payload)
        start, end = (int(value) for value in header.removeprefix("bytes=").split("-"))
        served.append(end - start + 1)
        return httpx2.Response(206, content=payload[start : end + 1])

    return httpx2.MockTransport(handler)


def test_download_zip_member_fetches_only_that_member(tmp_path, monkeypatch):
    # Bloques pequeños frente al ZIP de prueba, como 4 MB frente a los 556 MB reales.
    monkeypatch.setattr(http, "RANGE_CHUNK_BYTES", 16 * 1024)
    payload, sonora = make_nested_zip()
    served = []
    client = HttpClient(
        file_policy=FilePolicy(on_exists=OnExists.SKIP),
        transport=range_server(payload, served),
    )

    destination = tmp_path / "raw" / "26_sonora.zip"
    client.download_zip_member("https://example.com/national.zip", "26_sonora.zip", destination)

    assert destination.read_bytes() == sonora
    # Solo el índice y el miembro pedido, no los otros dos estados.
    assert sum(served) < len(payload) / 2


def test_download_zip_member_requires_range_support(tmp_path):
    payload, _ = make_nested_zip()
    client = HttpClient(
        file_policy=FilePolicy(on_exists=OnExists.SKIP),
        transport=range_server(payload, [], honor_ranges=False),
    )

    destination = tmp_path / "26_sonora.zip"
    with pytest.raises(ValueError, match="rango"):
        client.download_zip_member("https://example.com/national.zip", "26_sonora.zip", destination)

    assert list(tmp_path.iterdir()) == []


def test_download_zip_member_skips_when_policy_says_no(tmp_path):
    payload, _ = make_nested_zip()
    served = []
    client = HttpClient(
        file_policy=FilePolicy(on_exists=OnExists.SKIP),
        transport=range_server(payload, served),
    )

    destination = tmp_path / "26_sonora.zip"
    destination.write_bytes(b"old")
    client.download_zip_member("https://example.com/national.zip", "26_sonora.zip", destination)

    assert served == []
    assert destination.read_bytes() == b"old"
