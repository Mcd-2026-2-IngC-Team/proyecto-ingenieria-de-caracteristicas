from pathlib import Path

import geopandas as gpd
from loguru import logger

from project_name.config import load_dataset_config, load_logging, load_params
from project_name.features import SUBC_COLUMNAS_UTILES
from project_name.jobs.process_subcuencas_job import leer_capa
from project_name.logging import log_execution

# La "ciudad" se aproxima con los asentamientos del DCAH de la localidad 0001
# (Hermosillo); el mismo convenio que HERMOSILLO_CITY en process_ubicaciones_aviso_job.
CIUDAD_LOCALIDAD = "0001"


@log_execution
def process_hidrografia_cd_hermosillo(params: dict) -> None:
    subc_ds = load_dataset_config(params, source="inegi", dataset="subc_hermosillo")
    ciudad_ds = load_dataset_config(params, source="inegi", dataset="hidrografia_cd_hermosillo")
    colonias_ds = load_dataset_config(params, source="agua_hermosillo", dataset="colonias_hermosillo")

    gpkg_consolidado = (
        Path(subc_ds["processed"]["directory"]) / subc_ds["processed"]["filename"]
    )
    # El gpkg de colonias lo escribe process_colonias_hermosillo_job junto al CSV.
    colonias_gpkg = (
        Path(colonias_ds["processed"]["directory"]) / colonias_ds["processed"]["filename"]
    ).with_suffix(".gpkg")

    for processed_file in (gpkg_consolidado, colonias_gpkg):
        if not processed_file.exists():
            raise FileNotFoundError(f"{processed_file} not found: run `make data` first")

    colonias = gpd.read_file(colonias_gpkg)
    ciudad = colonias.loc[
        colonias["locality_code"] == CIUDAD_LOCALIDAD, "geometry"
    ].union_all()
    logger.info(
        "City polygon from {} settlements (locality_code {})",
        int((colonias["locality_code"] == CIUDAD_LOCALIDAD).sum()),
        CIUDAD_LOCALIDAD,
    )

    gpkg_ciudad = Path(ciudad_ds["processed"]["directory"]) / ciudad_ds["processed"]["filename"]
    gpkg_ciudad.parent.mkdir(parents=True, exist_ok=True)
    if gpkg_ciudad.exists():
        gpkg_ciudad.unlink()

    print(f"Creando GeoPackage de la ciudad: {gpkg_ciudad}")

    for sufijo in SUBC_COLUMNAS_UTILES:
        nombre_capa = sufijo.lstrip("_")
        capa = leer_capa(gpkg_consolidado, nombre_capa)

        ciudad_en_crs = gpd.GeoSeries([ciudad], crs=colonias.crs).to_crs(capa.crs)
        recortada = gpd.clip(capa, ciudad_en_crs)

        recortada.to_file(gpkg_ciudad, layer=nombre_capa, driver="GPKG")
        logger.info("Layer {} clipped to the city: {} rows", nombre_capa, len(recortada))


if __name__ == "__main__":
    params = load_params()

    load_logging(
        level=params["logging"]["level"],
        log_file=Path(params["logging"]["file"]),
        console=params["logging"].get("console", False),
    )

    process_hidrografia_cd_hermosillo(params)
