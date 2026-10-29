# /// script
# requires-python = ">=3.12,<3.14"
# dependencies = [
#     "ydata-profiling==4.18.4",
#     "pyyaml>=6.0.3",
#     "pyogrio>=0.11",
#     "geopandas>=1.1",
#     "setuptools<81",
# ]
# ///
"""Reporte automático (auto EDA) de cada dataset tidy con ydata-profiling.

ydata-profiling 4.18 exige pandas<3 y matplotlib<=3.10, y el proyecto usa pandas 3, así
que este script corre en su propio entorno aislado (dependencias en el encabezado PEP 723):

    uv run --script scripts/ydata_profile.py publicaciones_aguah

Escribe dos archivos por dataset:

- docs/eda/<dataset>.html: el reporte completo, para la página del proyecto.
- data/interim/eda/<dataset>.json: el mismo reporte en JSON, del que los notebooks de EDA
  leen el resumen y las alertas.
"""

from pathlib import Path
import sys

import pandas as pd
import pyogrio
import yaml
from ydata_profiling import ProfileReport

PROJECT_ROOT = Path(__file__).resolve().parent.parent
HTML_DIR = PROJECT_ROOT / "docs" / "eda"
JSON_DIR = PROJECT_ROOT / "data" / "interim" / "eda"

# Cómo leer cada CSV para que ydata no confunda claves con números: las claves del
# INEGI llevan ceros a la izquierda y los post_id son identificadores, no cantidades.
READ_OPTIONS = {
    "colonias_hermosillo": {
        "dtype": {"colonia_id": str, "locality_code": str, "postal_code": str},
    },
    "publicaciones_aguah": {
        "dtype": {"post_id": str},
        # post_id es la llave: como índice no entra en las correlaciones del reporte.
        "index_col": "post_id",
        "parse_dates": ["published_at", "announced_start_at"],
        # El texto vacío es un dato ("no trae texto"), no un faltante.
        "keep_default_na": False,
        "na_values": {"angry_share": [""], "announced_duration_hours": [""]},
    },
    "ubicaciones_aviso": {
        "dtype": {"post_id": str, "colonia_id": str},
    },
}

TITLES = {
    "colonias_hermosillo": "Colonias de Hermosillo (DCAH 2025)",
    "publicaciones_aguah": "Publicaciones de Agua de Hermosillo en Facebook",
    "ubicaciones_aviso": "Ubicaciones mencionadas en los avisos",
    "subc_hermosillo": "Red hidrográfica de las subcuencas de Hermosillo",
}

# Título legible de cada capa del GeoPackage consolidado.
LAYER_NAMES = {
    "hl": "red hidrográfica",
    "dr": "puntos de drenaje",
    "subc": "unidades de captación",
    "ha": "cuerpos de agua",
    "to": "topónimos",
}


def processed_path(dataset: str) -> Path:
    params = yaml.safe_load((PROJECT_ROOT / "params.yml").read_text())
    for source in params["sources"].values():
        config = source["datasets"].get(dataset, {}).get("processed")
        if config:
            return PROJECT_ROOT / config["directory"] / config["filename"]
    raise KeyError(f"{dataset} no tiene salida processed en params.yml")


def write_report(frame: pd.DataFrame, name: str, title: str) -> None:
    report = ProfileReport(
        frame,
        title=title,
        explorative=True,
        # Las interacciones (un scatter por par de numéricas) inflan el HTML sin aportar
        # más que la matriz de correlaciones, que los notebooks analizan aparte.
        interactions={"continuous": False},
        samples={"head": 5, "tail": 0, "random": 0},
        progress_bar=False,
    )

    HTML_DIR.mkdir(parents=True, exist_ok=True)
    JSON_DIR.mkdir(parents=True, exist_ok=True)
    report.to_file(HTML_DIR / f"{name}.html")
    report.to_file(JSON_DIR / f"{name}.json")


def profile(dataset: str) -> None:
    path = processed_path(dataset)

    # Un GeoPackage trae varias capas: un reporte por capa, sin la geometría.
    if path.suffix == ".gpkg":
        for layer in pyogrio.list_layers(path)[:, 0]:
            frame = pyogrio.read_dataframe(path, layer=layer, read_geometry=False)
            write_report(
                frame,
                f"{dataset}_{layer}",
                f"{TITLES[dataset]} — {LAYER_NAMES[layer]}",
            )
        return

    frame = pd.read_csv(path, **READ_OPTIONS[dataset])
    # Con keep_default_na=False las fechas vacías llegan como texto; se convierten aquí.
    for column in READ_OPTIONS[dataset].get("parse_dates", []):
        frame[column] = pd.to_datetime(frame[column].replace("", None))

    write_report(frame, dataset, TITLES[dataset])


if __name__ == "__main__":
    datasets = sys.argv[1:] or list(TITLES)
    for name in datasets:
        profile(name)
        print(f"{name}: {HTML_DIR}")
