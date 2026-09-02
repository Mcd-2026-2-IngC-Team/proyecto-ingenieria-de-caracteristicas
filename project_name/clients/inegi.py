from pathlib import Path

from project_name.clients.http import HttpClient


class InegiClient:
    def __init__(self, http_client: HttpClient):
        self.http_client = http_client

    def download(self, url: str, destination: Path) -> None:
        self.http_client.download(url, destination)
