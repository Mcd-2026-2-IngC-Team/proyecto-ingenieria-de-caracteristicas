import argparse
from datetime import UTC, datetime
from importlib import metadata
import json
import os
from pathlib import Path
import platform
import subprocess

from loguru import logger
import pandas as pd

from project_name.clients.ocr import OcrClient
from project_name.config import load_logging, load_params
from project_name.logging import log_execution

DEFAULT_DEVICE = "auto"
DEFAULT_OUTPUT_DIR = Path("data/external/facebook/ocr")
PROVENANCE_PACKAGES = ("paddleocr", "paddlex", "torch", "transformers")


def package_version(name: str) -> str | None:
    try:
        return metadata.version(name)
    except metadata.PackageNotFoundError:
        return None


def git_commit() -> str | None:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"], capture_output=True, text=True, check=True
        )
    except (OSError, subprocess.CalledProcessError):
        return None
    return result.stdout.strip()


def build_provenance(manifest: Path, device: str, counts: dict[str, int]) -> dict:
    # El OCR no es reproducible bit a bit (depende de hardware y versiones), así
    # que dejamos registrado con qué se generó cada CSV.
    return {
        "generated_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "manifest": str(manifest),
        "device": device,
        "hostname": platform.node(),
        "slurm_job_id": os.environ.get("SLURM_JOB_ID"),
        "git_commit": git_commit(),
        "packages": {name: package_version(name) for name in PROVENANCE_PACKAGES},
        "counts": counts,
    }


@log_execution
def ocr_images(
    manifest: Path, output_dir: Path = DEFAULT_OUTPUT_DIR, device: str = DEFAULT_DEVICE
) -> dict[str, int]:
    manifest_df = pd.read_csv(manifest)
    images_dir = manifest.parent
    client = OcrClient(device=device)

    counts = {"ocr_success": 0, "ocr_failed": 0, "skipped_no_image": 0}
    rows = []

    for _, row in manifest_df.iterrows():
        if row["status"] != "downloaded":
            counts["skipped_no_image"] += 1
            rows.append(
                {
                    "id": row["id"],
                    "filename": row["filename"],
                    "text": None,
                    "status": "skipped_no_image",
                }
            )
            continue

        try:
            text = client.extract_text(images_dir / row["filename"])
            counts["ocr_success"] += 1
            rows.append(
                {
                    "id": row["id"],
                    "filename": row["filename"],
                    "text": text,
                    "status": "ocr_success",
                }
            )
        except Exception as error:  # noqa: BLE001 - one bad image must not abort the batch
            logger.opt(exception=True).warning(
                "Failed OCR on {} (id={}): {}", row["filename"], row["id"], error
            )
            counts["ocr_failed"] += 1
            rows.append(
                {
                    "id": row["id"],
                    "filename": row["filename"],
                    "text": None,
                    "status": "ocr_failed",
                }
            )

    # Una subcarpeta por CSV de origen, igual que las imágenes, para que los
    # distintos rangos de fecha no se pisen entre sí.
    ocr_dir = output_dir / images_dir.name
    ocr_dir.mkdir(parents=True, exist_ok=True)
    ocr_path = ocr_dir / f"ocr_{manifest.stem.removeprefix('manifest_')}.csv"
    pd.DataFrame(rows).to_csv(ocr_path, index=False)
    logger.info("Wrote OCR results → {}", ocr_path)

    meta_path = ocr_path.with_suffix(".meta.json")
    provenance = build_provenance(manifest, device, counts)
    meta_path.write_text(json.dumps(provenance, indent=2, ensure_ascii=False) + "\n")

    logger.info("Summary: {}", counts)
    return counts


@log_execution
def ocr_image(image: Path, device: str = DEFAULT_DEVICE) -> str:
    client = OcrClient(device=device)
    return client.extract_text(image)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Corre OCR sobre las imágenes de un manifest, o sobre una sola imagen"
    )
    target = parser.add_mutually_exclusive_group(required=True)
    target.add_argument(
        "--manifest",
        type=Path,
        help="Ruta al manifest_<columna>.csv generado por extract_images_job",
    )
    target.add_argument(
        "--image",
        type=Path,
        help="Ruta a una sola imagen; imprime el texto extraído, no escribe CSV",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=None,
        help="Override de la carpeta de salida de params.yml (ocr.output_dir)",
    )
    parser.add_argument(
        "--device", default=None, help="Override del device de params.yml (ocr.device)"
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

    ocr_config = params.get("ocr", {})
    device = args.device or ocr_config.get("device", DEFAULT_DEVICE)

    if args.image:
        print(ocr_image(image=args.image, device=device))
    else:
        output_dir = args.output_dir or Path(ocr_config.get("output_dir", DEFAULT_OUTPUT_DIR))
        ocr_images(manifest=args.manifest, output_dir=output_dir, device=device)


if __name__ == "__main__":
    main()
