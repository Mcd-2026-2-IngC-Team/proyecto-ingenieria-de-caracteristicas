from pathlib import Path

from project_name.clients.inegi import InegiClient


class FakeHttpClient:
    def __init__(self):
        self.calls = []

    def download(self, url, destination):
        self.calls.append((url, destination))


def test_inegi_client_forwards_download_to_http_client():
    http_client = FakeHttpClient()
    client = InegiClient(http_client=http_client)

    client.download(url="https://example.com/file.zip", destination=Path("data/raw/file.zip"))

    assert http_client.calls == [("https://example.com/file.zip", Path("data/raw/file.zip"))]
