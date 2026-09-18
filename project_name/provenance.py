from datetime import UTC, datetime
import hashlib
from pathlib import Path
import textwrap

from loguru import logger

SOURCE_DESCRIPTION_FILENAME = "FUENTE.txt"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _utc(timestamp: float) -> str:
    return datetime.fromtimestamp(timestamp, UTC).strftime("%Y-%m-%d %H:%M")


def _indented(text: str) -> str:
    # El YAML trae la descripción partida en varias líneas; la reacomodamos a lo ancho.
    return textwrap.fill(
        " ".join(text.split()), width=88, initial_indent="  ", subsequent_indent="  "
    )


def write_source_description(
    source: dict,
    dataset: dict,
    files: list[Path],
    job: str,
    members: list[str] | None = None,
) -> Path:
    """Escribe `FUENTE.txt` junto a los datos crudos: de dónde vienen, qué son y cuándo
    se descargaron.

    La fecha de descarga es la fecha de modificación de cada archivo: la descarga
    atómica del cliente HTTP la fija al terminar, y la política `skip` no la toca, así
    que sigue siendo correcta aunque el job se vuelva a correr sin descargar.
    """
    source_line = source["name"] + (f" ({source['url']})" if source.get("url") else "")
    download_line = dataset["url"]
    if members:
        download_line += f"\n  Solo se descargó, por rango: {', '.join(members)}"

    lines = [dataset["name"], f"Fuente: {source_line}", f"Descarga: {download_line}"]

    if dataset.get("description"):
        lines += ["", "Descripción", _indented(dataset["description"])]
    if dataset.get("documentation"):
        lines += ["", "Documentación"] + [f"  - {url}" for url in dataset["documentation"]]
    if source.get("license"):
        lines += ["", f"Licencia: {source['license']}"]

    lines += ["", "Archivos (fecha de descarga según la fecha del archivo, UTC)"]
    for path in files:
        stats = path.stat()
        lines.append(
            f"  {path.name:<28} {stats.st_size / 1e6:>8.1f} MB   {_utc(stats.st_mtime)}"
            f"   sha256 {sha256(path)}"
        )

    lines += ["", f"Generado por {job} el {_utc(datetime.now(UTC).timestamp())} UTC"]

    destination = Path(dataset["raw"]["directory"]) / SOURCE_DESCRIPTION_FILENAME
    destination.write_text("\n".join(lines) + "\n", encoding="utf-8")
    logger.info("Wrote source description → {}", destination)
    return destination
