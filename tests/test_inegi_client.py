from pathlib import Path

from project_name.clients.inegi import InegiClient


class FakeHttpClient:
    def __init__(self):
        self.calls = []

    def download(self, url, destination):
        self.calls.append((url, destination))

    def download_zip_member(self, url, member, destination):
        self.calls.append((url, member, destination))


def test_inegi_client_forwards_download_to_http_client():
    http_client = FakeHttpClient()
    client = InegiClient(http_client=http_client)

    client.download(url="https://example.com/file.zip", destination=Path("data/raw/file.zip"))

    assert http_client.calls == [("https://example.com/file.zip", Path("data/raw/file.zip"))]


def test_inegi_client_forwards_zip_member_download_to_http_client():
    http_client = FakeHttpClient()
    client = InegiClient(http_client=http_client)

    client.download_zip_member(
        url="https://example.com/national.zip",
        member="26_sonora.zip",
        destination=Path("data/raw/sonora.zip"),
    )

    assert http_client.calls == [
        ("https://example.com/national.zip", "26_sonora.zip", Path("data/raw/sonora.zip"))
    ]
