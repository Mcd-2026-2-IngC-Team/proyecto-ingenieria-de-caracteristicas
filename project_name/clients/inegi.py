from pathlib import Path

from project_name.clients.http import HttpClient


class InegiClient:
    def __init__(self, http_client: HttpClient):
        self.http_client = http_client

    def download(self, url: str, destination: Path) -> None:
        self.http_client.download(url, destination)

    def download_zip_member(self, url: str, member: str, destination: Path) -> None:
        # Algunos productos del INEGI solo se publican como paquete nacional con un
        # ZIP por estado adentro (p. ej. la delimitación de colonias, ~556 MB);
        # así bajamos solo el estado que nos interesa.
        self.http_client.download_zip_member(url, member, destination)
