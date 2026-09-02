from pathlib import Path
import zipfile

from loguru import logger
import pandas as pd

from project_name.config import load_dataset_config, load_logging, load_params
from project_name.features import build_denue_features
from project_name.logging import log_execution


@log_execution
def process_denue_sonora(params: dict) -> None:
    dataset = load_dataset_config(
        params,
        source="inegi",
        dataset="denue_sonora_2024_05",
    )

    raw_file = Path(dataset["raw"]["directory"]) / dataset["raw"]["filename"]
    interim_dir = Path(dataset["interim"]["directory"])
    interim_dir.mkdir(parents=True, exist_ok=True)

    logger.info("Extracting {} → {}", raw_file, interim_dir)
    interim_root = interim_dir.resolve()
    with zipfile.ZipFile(raw_file, "r") as archive:
        for member in archive.infolist():
            extracted_path = (interim_root / member.filename).resolve()
            if interim_root not in extracted_path.parents and extracted_path != interim_root:
                raise ValueError(f"Unsafe path in zip: {member.filename}")
        archive.extractall(interim_dir)
    csv_file = next((interim_dir / "conjunto_de_datos").glob("*.csv"))
    logger.info("Found data file: {}", csv_file)

    # El INEGI publica estos archivos en ISO-8859-1, no UTF-8; utf-8 lanza UnicodeDecodeError.
    # low_memory=False evita un DtypeWarning al inferir el tipo de columnas mixtas (ej. telefono).
    df = pd.read_csv(csv_file, encoding="latin-1", low_memory=False)
    logger.info("Read {} rows, {} columns", df.shape[0], df.shape[1])

    denue = build_denue_features(df)
    logger.info("Built {} feature rows", len(denue))

    processed_dir = Path(dataset["processed"]["directory"])
    processed_dir.mkdir(parents=True, exist_ok=True)
    processed_file = processed_dir / dataset["processed"]["filename"]
    denue.to_csv(processed_file, index=False)
    logger.info("Wrote processed data → {}", processed_file)


if __name__ == "__main__":
    params = load_params()

    load_logging(
        level=params["logging"]["level"],
        log_file=Path(params["logging"]["file"]),
    )

    process_denue_sonora(params)
