from pathlib import Path

import pandas as pd

from project_name.config import load_dataset_config, load_logging, load_params
from project_name.logging import log_execution


@log_execution
def process_bachometro(params: dict) -> None:
    dataset = load_dataset_config(
        params,
        source="bachometro",
        dataset="baches",
    )

    raw_directory = Path(dataset["raw"]["directory"])

    processed_directory = Path(dataset["processed"]["directory"])

    output_file = (
        processed_directory
        / dataset["processed"]["filename"]
    )

    dataframes = []

    for year in dataset["years"]:
        input_file = (
            raw_directory
            / dataset["raw"]["filename"].format(year=year)
        )

        if not input_file.exists():
            raise FileNotFoundError(
                f"No se encontró el archivo de Bachómetro para {year}: "
                f"{input_file}"
            )

        # Leer JSON generado por el ingest job
        df_year = pd.read_json(input_file)

        # Agregar año de procedencia
        df_year["year"] = year

        # Conversiones básicas de tipos
        df_year["latitude"] = pd.to_numeric(
            df_year["latitude"]
        )

        df_year["longitude"] = pd.to_numeric(
            df_year["longitude"]
        )

        df_year["date"] = pd.to_datetime(
            df_year["date"]
        )

        # Fecha en formato mexicano
        df_year["date_mx"] = (
            df_year["date"]
            .dt.strftime("%d/%m/%Y")
        )

        dataframes.append(df_year)

        print(f"{year}: {len(df_year)} reportes")

    # Combinar todos los años
    df = pd.concat(
        dataframes,
        ignore_index=True,
    )
    df.insert(0, "id_row", range(1, len(df) + 1))

    # Crear directorio processed si no existe
    processed_directory.mkdir(
        parents=True,
        exist_ok=True,
    )

    # Guardar CSV
    df.to_csv(
        output_file,
        index=False,
    )

    print("null values")
    print(df.isna().sum())


if __name__ == "__main__":
    params = load_params()

    load_logging(
        level=params["logging"]["level"],
        log_file=Path(params["logging"]["file"]),
        console=params["logging"].get("console", False),
    )

    process_bachometro(params)