from pathlib import Path

from project_name.clients.http import HttpClient


class BachometroClient:
    def __init__(self, http_client: HttpClient):
        self.http_client = http_client

    def download_year(
        self,
        *,
        url: str,
        year: int,
        destination: Path,
    ) -> None:
        self.http_client.download(
            url=f"{url}?year={year}",
            destination=destination,
        )