from pathlib import Path

import geopandas as gpd
from loguru import logger

from project_name.config import load_dataset_config, load_logging, load_params
from project_name.geocoding import GEOGRAPHIC, build_colonias
from project_name.logging import log_execution


@log_execution
def process_colonias_hermosillo(params: dict) -> None:
    dcah = load_dataset_config(params, source="inegi", dataset="dcah_2025")
    dataset = load_dataset_config(params, source="agua_hermosillo", dataset="colonias_hermosillo")

    settlements_file = Path(dcah["interim"]["directory"]) / "conjunto_de_datos" / "26as.shp"
    if not settlements_file.exists():
        raise FileNotFoundError(f"{settlements_file} not found: run `make data` first")

    colonias = build_colonias(gpd.read_file(settlements_file))
    if not colonias["colonia_id"].is_unique:
        raise ValueError("cvegeo se repite entre los asentamientos de Hermosillo")
    logger.info("Built {} settlements", len(colonias))

    processed_dir = Path(dataset["processed"]["directory"])
    processed_dir.mkdir(parents=True, exist_ok=True)
    processed_file = processed_dir / dataset["processed"]["filename"]
    colonias.drop(columns="geometry").to_csv(processed_file, index=False)
    logger.info("Wrote processed data → {}", processed_file)

    # El polígono va aparte: el CSV es la tabla tidy y el GeoPackage la geometría, que es
    # lo que el tablero necesita para pintar el mapa por colonia.
    geo_file = processed_file.with_suffix(".gpkg")
    colonias.to_crs(epsg=GEOGRAPHIC).to_file(geo_file, driver="GPKG")
    logger.info("Wrote polygons → {}", geo_file)


if __name__ == "__main__":
    params = load_params()

    load_logging(
        level=params["logging"]["level"],
        log_file=Path(params["logging"]["file"]),
        console=params["logging"].get("console", False),
    )

    process_colonias_hermosillo(params)
