import argparse
from datetime import UTC, datetime
from pathlib import Path
import sys
import tarfile

from loguru import logger

from project_name.config import PROJECT_ROOT, load_logging, load_params
from project_name.constants import EXTERNAL_DIR
from project_name.logging import log_execution
from project_name.provenance import sha256

# data/external no es reproducible (scraper de paga, URLs que expiran, OCR que
# depende del hardware): se congela en un snapshot y en git solo se versionan
# sus checksums, para que cualquiera verifique que tiene exactamente los mismos datos.
CHECKSUMS_FILE = PROJECT_ROOT / "data" / "external.sha256"
BACKUPS_DIR = PROJECT_ROOT / "backups"
IGNORED_NAMES = {".DS_Store", ".gitkeep"}


def list_files(root: Path) -> list[Path]:
    return sorted(
        path for path in root.rglob("*") if path.is_file() and path.name not in IGNORED_NAMES
    )


def compute_checksums(root: Path) -> dict[str, str]:
    return {path.relative_to(root).as_posix(): sha256(path) for path in list_files(root)}


def read_checksums(checksums_file: Path) -> dict[str, str]:
    checksums = {}
    for line in checksums_file.read_text().splitlines():
        digest, relative_path = line.split("  ", 1)
        checksums[relative_path] = digest
    return checksums


@log_execution
def write_snapshot(root: Path, checksums_file: Path, backups_dir: Path) -> Path:
    checksums = compute_checksums(root)
    checksums_file.write_text("".join(f"{digest}  {path}\n" for path, digest in checksums.items()))
    logger.info("Wrote {} checksums → {}", len(checksums), checksums_file)

    backups_dir.mkdir(parents=True, exist_ok=True)
    archive = backups_dir / f"external_snapshot_{datetime.now(UTC):%Y%m%d}.tar.gz"
    with tarfile.open(archive, "w:gz") as tar:
        for relative_path in checksums:
            tar.add(root / relative_path, arcname=f"external/{relative_path}")
    logger.info("Wrote snapshot archive → {}", archive)
    return archive


@log_execution
def verify_snapshot(root: Path, checksums_file: Path) -> dict[str, list[str]]:
    expected = read_checksums(checksums_file)
    actual = compute_checksums(root)

    problems = {
        "missing": sorted(expected.keys() - actual.keys()),
        "changed": sorted(p for p in expected.keys() & actual.keys() if expected[p] != actual[p]),
        "unexpected": sorted(actual.keys() - expected.keys()),
    }
    logger.info("Verified {} files: {}", len(expected), {k: len(v) for k, v in problems.items()})
    return problems


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Congela data/external (checksums + tar.gz) o verifica una copia descargada"
    )
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument(
        "--write", action="store_true", help="Escribe data/external.sha256 y el tar.gz"
    )
    mode.add_argument(
        "--verify", action="store_true", help="Compara data/external contra data/external.sha256"
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

    if args.write:
        archive = write_snapshot(EXTERNAL_DIR, CHECKSUMS_FILE, BACKUPS_DIR)
        print(f"Checksums: {CHECKSUMS_FILE.relative_to(PROJECT_ROOT)}")
        print(f"Snapshot:  {archive.relative_to(PROJECT_ROOT)}  (súbelo a OneDrive)")
        return

    problems = verify_snapshot(EXTERNAL_DIR, CHECKSUMS_FILE)
    for kind, paths in problems.items():
        for path in paths:
            print(f"{kind}: {path}")
    if any(problems.values()):
        sys.exit(1)
    print("data/external coincide con data/external.sha256")


if __name__ == "__main__":
    main()
