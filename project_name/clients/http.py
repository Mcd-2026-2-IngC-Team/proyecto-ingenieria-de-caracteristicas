from collections.abc import Iterator
from contextlib import contextmanager
import io
from pathlib import Path
import shutil
from typing import BinaryIO
import zipfile

import httpx2
from loguru import logger

from project_name.policies.file import FilePolicy

# httpx corta por defecto a los 5 s sin recibir datos; algunos servidores (el del
# INEGI, por ejemplo) se pausan más que eso a media descarga.
DEFAULT_TIMEOUT_SECONDS = 60.0
RANGE_CHUNK_BYTES = 4 * 1024 * 1024


class HttpClient:
    def __init__(
        self,
        file_policy: FilePolicy,
        timeout: float = DEFAULT_TIMEOUT_SECONDS,
        transport: httpx2.BaseTransport | None = None,
    ):
        self.file_policy = file_policy
        self.timeout = timeout
        # Solo para pruebas: permite inyectar un httpx2.MockTransport.
        self.transport = transport

    def download(self, url: str, destination: Path) -> None:
        if not self.file_policy.should_write(destination):
            logger.info("Skipping existing file: {}", destination)
            return
        logger.info("Downloading {} → {}", url, destination)
        destination.parent.mkdir(parents=True, exist_ok=True)

        with (
            _atomic_write(destination) as file,
            httpx2.stream("GET", url, follow_redirects=True, timeout=self.timeout) as response,
        ):
            response.raise_for_status()
            for chunk in response.iter_bytes():
                file.write(chunk)
        logger.info("Download completed: {}", destination)

    def download_zip_member(self, url: str, member: str, destination: Path) -> None:
        """Descarga un solo archivo de un ZIP remoto sin bajar el ZIP completo.

        Lee el índice del ZIP (al final del archivo) y luego solo los bytes del
        miembro pedido, con peticiones HTTP por rangos. Requiere que el servidor
        responda 206 a los encabezados Range.
        """
        if not self.file_policy.should_write(destination):
            logger.info("Skipping existing file: {}", destination)
            return
        logger.info("Downloading member {} of {} → {}", member, url, destination)
        destination.parent.mkdir(parents=True, exist_ok=True)

        with httpx2.Client(
            follow_redirects=True, timeout=self.timeout, transport=self.transport
        ) as session:
            remote = io.BufferedReader(_RangeReader(session, url), buffer_size=RANGE_CHUNK_BYTES)
            with (
                zipfile.ZipFile(remote) as archive,
                archive.open(member) as source,
                _atomic_write(destination) as file,
            ):
                shutil.copyfileobj(source, file, RANGE_CHUNK_BYTES)
        logger.info("Download completed: {}", destination)


@contextmanager
def _atomic_write(destination: Path) -> Iterator[BinaryIO]:
    """Escribe en `<destino>.part` y solo al terminar lo renombra al destino.

    Así una descarga interrumpida nunca queda con el nombre final, donde la
    política `skip` la daría por buena en la siguiente corrida.
    """
    partial = destination.with_name(destination.name + ".part")
    try:
        with partial.open("wb") as file:
            yield file
    except BaseException:
        partial.unlink(missing_ok=True)
        raise
    partial.replace(destination)


class _RangeReader(io.RawIOBase):
    """Archivo remoto de solo lectura: cada lectura es una petición HTTP por rango."""

    def __init__(self, session: httpx2.Client, url: str):
        self.session = session
        self.url = url
        self.position = 0
        response = session.head(url)
        response.raise_for_status()
        self.size = int(response.headers["Content-Length"])

    def readable(self) -> bool:
        return True

    def seekable(self) -> bool:
        return True

    def tell(self) -> int:
        return self.position

    def seek(self, offset: int, whence: int = io.SEEK_SET) -> int:
        base = {io.SEEK_SET: 0, io.SEEK_CUR: self.position, io.SEEK_END: self.size}[whence]
        self.position = base + offset
        return self.position

    def readinto(self, buffer) -> int:
        if self.position >= self.size or len(buffer) == 0:
            return 0
        end = min(self.size, self.position + len(buffer)) - 1
        response = self.session.get(self.url, headers={"Range": f"bytes={self.position}-{end}"})
        response.raise_for_status()
        if response.status_code != 206:
            raise ValueError(f"El servidor no admite descargas por rango: {self.url}")
        data = response.content
        buffer[: len(data)] = data
        self.position += len(data)
        return len(data)
