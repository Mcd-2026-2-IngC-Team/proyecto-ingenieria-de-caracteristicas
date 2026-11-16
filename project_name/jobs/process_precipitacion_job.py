import json
from pathlib import Path

import pandas as pd

from project_name.config import load_dataset_config, load_logging, load_params
from project_name.logging import log_execution


def build_precipitacion(payload: dict) -> pd.DataFrame:
    """Tabla tidy de un día por fila a partir de la respuesta JSON de Open-Meteo."""
    daily = payload["daily"]
    frame = pd.DataFrame(
        {
            "date": pd.to_datetime(daily["time"]),
            "precipitation_mm": pd.to_numeric(daily["precipitation_sum"]),
            "precipitation_hours": pd.to_numeric(daily["precipitation_hours"]),
        }
    )
    frame["year"] = frame["date"].dt.year
    frame["month"] = frame["date"].dt.month
    # Umbral de 1 mm: por debajo el reanálisis registra llovizna que no escurre.
    frame["is_rain_day"] = frame["precipitation_mm"] >= 1.0
    return frame


@log_execution
def process_precipitacion(params: dict) -> None:
    dataset = load_dataset_config(params, source="open_meteo", dataset="precipitacion_hermosillo")

    input_file = Path(dataset["raw"]["directory"]) / dataset["raw"]["filename"]
    processed_directory = Path(dataset["processed"]["directory"])
    output_file = processed_directory / dataset["processed"]["filename"]

    if not input_file.exists():
        raise FileNotFoundError(f"No se encontró el archivo de precipitación: {input_file}")

    frame = build_precipitacion(json.loads(input_file.read_text(encoding="utf-8")))
    print(f"{len(frame)} días, {int(frame['is_rain_day'].sum())} con lluvia de 1 mm o más")

    processed_directory.mkdir(parents=True, exist_ok=True)
    frame.to_csv(output_file, index=False)


if __name__ == "__main__":
    params = load_params()

    load_logging(
        level=params["logging"]["level"],
        log_file=Path(params["logging"]["file"]),
        console=params["logging"].get("console", False),
    )

    process_precipitacion(params)
