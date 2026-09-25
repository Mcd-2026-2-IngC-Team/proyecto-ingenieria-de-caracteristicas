from pathlib import Path
import zipfile

import geopandas as gpd
from loguru import logger

from project_name.config import load_dataset_config, load_logging, load_params
from project_name.geocoding import GEOGRAPHIC, build_colonias
from project_name.logging import log_execution


def safe_extract(archive: zipfile.ZipFile, destination: Path) -> None:
    # Rechaza cualquier miembro cuya ruta final quede fuera del destino (Zip Slip),
    # p. ej. un nombre como `../../algo`.
    root = destination.resolve()
    for member in archive.infolist():
        target = (root / member.filename).resolve()
        if root not in target.parents and target != root:
            raise ValueError(f"Unsafe path in zip: {member.filename}")
    archive.extractall(destination)


@log_execution
def process_colonias_hermosillo(params: dict) -> None:
    dcah = load_dataset_config(params, source="inegi", dataset="dcah_2025")
    dataset = load_dataset_config(params, source="agua_hermosillo", dataset="colonias_hermosillo")

    raw_file = Path(dcah["raw"]["directory"]) / dcah["raw"]["filename"]
    if not raw_file.exists():
        raise FileNotFoundError(f"{raw_file} not found: run `make download` first")

    # Se extrae en cada corrida para que data/interim siempre refleje el ZIP de data/raw;
    # process_ubicaciones_aviso lee la misma capa, por eso `make data` corre este job antes.
    interim_dir = Path(dcah["interim"]["directory"])
    interim_dir.mkdir(parents=True, exist_ok=True)
    logger.info("Extracting {} → {}", raw_file, interim_dir)
    with zipfile.ZipFile(raw_file) as archive:
        safe_extract(archive, interim_dir)

    settlements_file = interim_dir / "conjunto_de_datos" / "26as.shp"

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
