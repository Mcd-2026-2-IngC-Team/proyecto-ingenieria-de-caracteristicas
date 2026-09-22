"""Diccionario de datos: un archivo por cada dataset procesado, en CSV (references/,
para que GitHub lo renderice como tabla) y en JSON (references/json/).

Lo único escrito a mano son las descripciones de abajo; el tipo, los nulos, los valores
distintos y el rango los calcula pandas (dtype, isna, nunique, min/max) al generar los
archivos.

    uv run python -m project_name.metadata.dictionary
"""

import csv
from datetime import UTC, datetime
import json
from pathlib import Path

from loguru import logger
import pandas as pd

from project_name.config import PROJECT_ROOT, load_logging, load_params
from project_name.constants import REFERENCES_DIR
from project_name.logging import log_execution

REFERENCES_JSON_DIR = REFERENCES_DIR / "json"

# El rango (min/max) de una columna de texto libre expondría valores reales sin
# agregar, así que solo se publica para columnas que no son de texto. pandas 3 usa un
# dtype de texto dedicado (se imprime "str"), no "object", así que el tipo se detecta
# con is_string_dtype en vez de comparar el nombre del dtype.
TEXT_RANGE_NOTE = (
    "El rango de las columnas de texto no se publica: su mínimo y su máximo serían "
    "valores reales sin agregar."
)

# Qué representa una fila de cada dataset procesado (la "granularidad" de la tabla).
ROWS = {
    "denue_sonora_2024_05": "un establecimiento activo del DENUE en Sonora",
}

# Columnas que deben leerse como fecha: pandas no las infiere solo desde un CSV, así
# que se declaran a mano, igual que ROWS y DESCRIPTIONS.
DATE_COLUMNS = {
    "denue_sonora_2024_05": ["registration_date"],
}

DESCRIPTIONS = {
    "denue_sonora_2024_05": {
        "id": "Identificador del establecimiento en el DENUE",
        "business_name": "Nombre o razón social del establecimiento",
        "activity_code": "Código SCIAN de la actividad económica",
        "activity_name": "Nombre de la actividad económica (SCIAN)",
        "employee_range": "Rango de personal ocupado, en texto (ej. '0 a 5 personas')",
        "employee_range_rank": "Orden del rango de personal ocupado, de 1 (menor) a 7 (mayor)",
        "municipality": "Municipio del domicilio del establecimiento",
        "locality": "Localidad del domicilio del establecimiento",
        "latitude": "Latitud del establecimiento",
        "longitude": "Longitud del establecimiento",
        "registration_date": "Fecha de alta del establecimiento en el DENUE",
        "has_phone": "Si el establecimiento tiene teléfono registrado",
        "has_email": "Si el establecimiento tiene correo electrónico registrado",
    },
}


def processed_files(params: dict) -> dict[str, Path]:
    """Mapea cada dataset con salida procesada a la ruta de su archivo, según params.yml."""
    files = {}
    for source in params["sources"].values():
        for key, dataset in source["datasets"].items():
            processed = dataset.get("processed")
            if processed:
                files[key] = Path(processed["directory"]) / processed["filename"]
    return files


def _format_range(non_null: pd.Series) -> str:
    minimum, maximum = non_null.min(), non_null.max()
    if isinstance(minimum, pd.Timestamp):
        return f"{minimum.date()} – {maximum.date()}"
    return f"{minimum} – {maximum}"


def profile(csv_file: Path, dataset: str) -> tuple[int, list[dict]]:
    """Filas del CSV y, por columna, su tipo, nulos, valores distintos y rango."""
    df = pd.read_csv(csv_file, parse_dates=DATE_COLUMNS.get(dataset, []))

    columns = []
    for name in df.columns:
        series = df[name]
        non_null = series.dropna()
        is_text = pd.api.types.is_string_dtype(series.dtype)
        columns.append(
            {
                "column_name": name,
                "type": str(series.dtype),
                "nulos_pct": float(series.isna().mean() * 100),
                # nunique() es un conteo exacto, no una estimación: en un diccionario de
                # datos eso importa, p. ej. para ver que una llave no se repite.
                "distintos": int(series.nunique(dropna=True)),
                "rango": None if is_text or non_null.empty else _format_range(non_null),
                "is_text": is_text,
            }
        )
    return len(df), columns


def document(dataset: str, csv_file: Path, n_rows: int, columns: list[dict]) -> dict:
    """El diccionario de un dataset, listo para escribirse como JSON."""
    descriptions = DESCRIPTIONS[dataset]
    shown = (
        csv_file.relative_to(PROJECT_ROOT) if csv_file.is_relative_to(PROJECT_ROOT) else csv_file
    )
    documented = {
        "dataset": dataset,
        "archivo": str(shown),
        "una_fila_es": ROWS[dataset],
        "filas": n_rows,
        "columnas": [
            {
                "nombre": column["column_name"],
                "tipo": column["type"],
                "nulos_pct": column["nulos_pct"],
                "distintos": column["distintos"],
                "rango": column["rango"],
                "descripcion": descriptions[column["column_name"]],
            }
            for column in columns
        ],
        "generado": {
            "fecha": datetime.now(UTC).strftime("%Y-%m-%d %H:%M UTC"),
            "comando": "make dictionary",
            "perfil": "pandas: dtype, isna(), nunique(), min()/max()",
        },
    }
    if any(column["is_text"] for column in columns):
        documented["nota"] = TEXT_RANGE_NOTE
    return documented


def write_csv(destination: Path, columns: list[dict]) -> None:
    fieldnames = ["nombre", "tipo", "nulos_pct", "distintos", "rango", "descripcion"]
    with destination.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(columns)


@log_execution
def build_dictionaries(params: dict) -> list[Path]:
    """Escribe un diccionario (CSV + JSON) por dataset procesado y devuelve las rutas.

    Falla si una columna no está descrita, o si se describe una que ya no existe: es lo
    que evita que el diccionario se quede atrás cuando cambian los datos.
    """
    REFERENCES_DIR.mkdir(parents=True, exist_ok=True)
    REFERENCES_JSON_DIR.mkdir(parents=True, exist_ok=True)

    written = []
    for dataset, csv_file in processed_files(params).items():
        if dataset not in DESCRIPTIONS:
            raise ValueError(f"{dataset}: falta describir sus columnas en dictionary.py")
        if not csv_file.exists():
            raise FileNotFoundError(f"{csv_file} not found: run `make data` first")

        n_rows, columns = profile(csv_file, dataset)
        descriptions = DESCRIPTIONS[dataset]
        undocumented = {column["column_name"] for column in columns} - set(descriptions)
        missing = set(descriptions) - {column["column_name"] for column in columns}
        if undocumented or missing:
            raise ValueError(
                f"{dataset}: columnas sin describir: {sorted(undocumented)}; "
                f"descritas pero inexistentes: {sorted(missing)}"
            )

        documented = document(dataset, csv_file, n_rows, columns)

        json_destination = REFERENCES_JSON_DIR / f"diccionario_{dataset}.json"
        json_destination.write_text(
            json.dumps(documented, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )

        csv_destination = REFERENCES_DIR / f"{dataset}.csv"
        write_csv(csv_destination, documented["columnas"])

        logger.info(
            "Documented {} columns → {}, {}", len(columns), csv_destination, json_destination
        )
        written += [csv_destination, json_destination]
    return written


def main() -> None:
    params = load_params()
    load_logging(
        level=params["logging"]["level"],
        log_file=Path(params["logging"]["file"]),
        console=params["logging"].get("console", False),
    )

    for destination in build_dictionaries(params):
        print(f"diccionario → {destination.relative_to(PROJECT_ROOT)}")


if __name__ == "__main__":
    main()
