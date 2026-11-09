import argparse
from datetime import UTC, datetime
from pathlib import Path
import sys
import tarfile

from loguru import logger

from project_name.config import PROJECT_ROOT, load_logging, load_params
from project_name.constants import EXTERNAL_DIR
from project_name.logging import log_execution
from project_name.metadata.source import sha256

# data/external no es reproducible (scraper de paga, URLs que expiran, OCR que
# depende del hardware): se congela en un snapshot y en git solo se versionan
# sus checksums, para que cualquiera verifique que tiene exactamente los mismos datos.
CHECKSUMS_FILE = PROJECT_ROOT / "data" / "external.sha256"
# Los archivos en PDU_FILES se descargan a mano de otro drive (ver data/SNAPSHOT.md):
# llevan su propio archivo de checksums y no viajan en el tar.gz del snapshot.
CHECKSUMS_PDU_FILE = PROJECT_ROOT / "data" / "external_PDU.sha256"
PDU_FILES = {"distritos_sectores_hermosillo_PDU_2025.csv"}
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
def write_snapshot(root: Path, backups_dir: Path) -> Path:
    checksums = compute_checksums(root)
    snapshot_checksums = {p: d for p, d in checksums.items() if p not in PDU_FILES}
    pdu_checksums = {p: d for p, d in checksums.items() if p in PDU_FILES}

    CHECKSUMS_FILE.write_text(
        "".join(f"{digest}  {path}\n" for path, digest in snapshot_checksums.items())
    )
    CHECKSUMS_PDU_FILE.write_text(
        "".join(f"{digest}  {path}\n" for path, digest in pdu_checksums.items())
    )
    logger.info(
        "Wrote {} + {} checksums → {} , {}",
        len(snapshot_checksums), len(pdu_checksums), CHECKSUMS_FILE, CHECKSUMS_PDU_FILE,
    )

    backups_dir.mkdir(parents=True, exist_ok=True)
    archive = backups_dir / f"external_snapshot_{datetime.now(UTC):%Y%m%d}.tar.gz"
    with tarfile.open(archive, "w:gz") as tar:
        for relative_path in snapshot_checksums:
            tar.add(root / relative_path, arcname=f"external/{relative_path}")
    logger.info("Wrote snapshot archive → {}", archive)
    return archive


@log_execution
def verify_snapshot(root: Path) -> dict[str, dict[str, list[str]]]:
    actual = compute_checksums(root)
    problems = {}
    for name, checksums_file, pdu_group in (
        ("data/external", CHECKSUMS_FILE, False),
        ("data/external (PDU)", CHECKSUMS_PDU_FILE, True),
    ):
        expected = read_checksums(checksums_file)
        actual_group = {p for p in actual if (p in PDU_FILES) == pdu_group}
        problems[name] = {
            "missing": sorted(expected.keys() - actual_group),
            "changed": sorted(
                p for p in expected.keys() & actual_group if expected[p] != actual[p]
            ),
            "unexpected": sorted(actual_group - expected.keys()),
        }
        logger.info(
            "Verified {} files in {}: {}",
            len(expected), name, {k: len(v) for k, v in problems[name].items()},
        )
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
        archive = write_snapshot(EXTERNAL_DIR, BACKUPS_DIR)
        print(f"Checksums: {CHECKSUMS_FILE.relative_to(PROJECT_ROOT)}")
        print(f"Checksums: {CHECKSUMS_PDU_FILE.relative_to(PROJECT_ROOT)}")
        print(f"Snapshot:  {archive.relative_to(PROJECT_ROOT)}  (súbelo a OneDrive)")
        return

    problems = verify_snapshot(EXTERNAL_DIR)
    for name, group in problems.items():
        for kind, paths in group.items():
            for path in paths:
                print(f"{name} - {kind}: {path}")
        if not any(group.values()):
            checksums_file = CHECKSUMS_PDU_FILE if "PDU" in name else CHECKSUMS_FILE
            print(f"{name} coincide con {checksums_file.relative_to(PROJECT_ROOT)}")
    if any(any(group.values()) for group in problems.values()):
        sys.exit(1)


if __name__ == "__main__":
    main()
