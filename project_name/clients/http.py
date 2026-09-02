from pathlib import Path

import httpx2
from loguru import logger

from project_name.policies.file import FilePolicy


class HttpClient:
    def __init__(self, file_policy: FilePolicy):
        self.file_policy = file_policy

    def download(self, url: str, destination: Path) -> None:
        if not self.file_policy.should_write(destination):
            logger.info("Skipping existing file: {}", destination)
            return
        logger.info("Downloading {} → {}", url, destination)
        destination.parent.mkdir(parents=True, exist_ok=True)

        with httpx2.stream("GET", url, follow_redirects=True) as response:
            response.raise_for_status()

            with destination.open("wb") as file:
                for chunk in response.iter_bytes():
                    file.write(chunk)
        logger.info("Download completed: {}", destination)
