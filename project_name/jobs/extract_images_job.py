import argparse
from pathlib import Path
import re
from urllib.parse import urlsplit

from loguru import logger
import pandas as pd

from project_name.clients.http import HttpClient
from project_name.config import load_logging, load_params
from project_name.logging import log_execution
from project_name.policies.file import FilePolicy, OnExists


def slugify(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9_-]+", "-", value).strip("-")


def build_filename(row_id: str, column_slug: str, url: str) -> str:
    ext = Path(urlsplit(str(url)).path).suffix or ".jpg"
    return f"{row_id}_{column_slug}{ext}"


@log_execution
def extract_images(
    source: Path,
    dest: Path,
    column: str,
    id_column: str,
    on_exists: OnExists = OnExists.SKIP,
) -> dict[str, int]:
    try:
        df = pd.read_csv(source, encoding="utf-8-sig", usecols=[column, id_column])
    except ValueError as error:
        raise ValueError(f"Column '{column}' or '{id_column}' not found in {source}") from error

    column_slug = slugify(column)
    output_dir = dest / source.stem
    output_dir.mkdir(parents=True, exist_ok=True)

    policy = FilePolicy(on_exists=on_exists)
    client = HttpClient(file_policy=policy)

    counts = {
        "downloaded": 0,
        "skipped_empty": 0,
        "skipped_missing_id": 0,
        "skipped_existing": 0,
        "failed": 0,
    }
    manifest_rows = []

    for row_index, row in df.iterrows():
        url = row[column]
        row_id = row[id_column]

        if pd.isna(row_id) or not str(row_id).strip():
            counts["skipped_missing_id"] += 1
            manifest_rows.append(
                {
                    "row_index": row_index,
                    "id": None,
                    "url": url,
                    "filename": None,
                    "status": "skipped_missing_id",
                }
            )
            continue

        if pd.isna(url) or not str(url).strip():
            counts["skipped_empty"] += 1
            manifest_rows.append(
                {
                    "row_index": row_index,
                    "id": row_id,
                    "url": url,
                    "filename": None,
                    "status": "skipped_empty",
                }
            )
            continue

        filename = build_filename(row_id, column_slug, url)
        destination = output_dir / filename

        if not policy.should_write(destination):
            counts["skipped_existing"] += 1
            manifest_rows.append(
                {
                    "row_index": row_index,
                    "id": row_id,
                    "url": url,
                    "filename": filename,
                    "status": "skipped_existing",
                }
            )
            continue

        try:
            client.download(url=url, destination=destination)
            counts["downloaded"] += 1
            manifest_rows.append(
                {
                    "row_index": row_index,
                    "id": row_id,
                    "url": url,
                    "filename": filename,
                    "status": "downloaded",
                }
            )
        except Exception as error:  # noqa: BLE001 - one bad/expired URL must not abort the batch
            logger.opt(exception=True).warning(
                "Failed row {} (id={}): {}", row_index, row_id, error
            )
            counts["failed"] += 1
            manifest_rows.append(
                {
                    "row_index": row_index,
                    "id": row_id,
                    "url": url,
                    "filename": filename,
                    "status": "failed",
                }
            )

    manifest_path = output_dir / f"manifest_{column_slug}.csv"
    pd.DataFrame(manifest_rows).to_csv(manifest_path, index=False)
    logger.info("Wrote manifest → {}", manifest_path)

    logger.info("Summary: {}", counts)
    return counts


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Descarga imágenes referenciadas en una columna de un CSV"
    )
    parser.add_argument("--source", required=True, type=Path, help="Ruta al CSV origen")
    parser.add_argument(
        "--dest", required=True, type=Path, help="Carpeta destino base para las imágenes"
    )
    parser.add_argument("--column", required=True, help="Columna del CSV con las URLs de imagen")
    parser.add_argument(
        "--id-column",
        required=True,
        help="Columna con un identificador único por fila (ej. postId)",
    )
    parser.add_argument(
        "--on-exists",
        choices=[value.value for value in OnExists],
        default=OnExists.SKIP.value,
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    params = load_params()
    load_logging(
        level=params["logging"]["level"],
        log_file=Path(params["logging"]["file"]),
        console=params["logging"].get("console", False),
    )

    extract_images(
        source=args.source,
        dest=args.dest,
        column=args.column,
        id_column=args.id_column,
        on_exists=OnExists(args.on_exists),
    )


if __name__ == "__main__":
    main()
