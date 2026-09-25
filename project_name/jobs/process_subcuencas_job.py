from pathlib import Path
import zipfile

from loguru import logger
import pandas as pd
import geopandas as gpd

from project_name.config import load_dataset_config, load_logging, load_params
from project_name.features import build_subcuencas_features
from project_name.logging import log_execution


@log_execution
def process_subcuencas(params: dict) -> None:
    subcuencas_dir_data = {
        "subc_r_san_miguel": "RH09/RH09D/RH09De",
        "subc_r_son_hillo": "RH09/RH09D/RH09Da",
        "subc_la_poza": "RH09/RH09D/RH09Di",
        "subc_la_manga": "RH09/RH09E/RH09Eb"
    }
    
    rutas_subcuencas = {}
    
    for nombre_dataset, dir_data in subcuencas_dir_data.items():
        dataset = load_dataset_config(
            params,
            source="inegi",
            dataset=nombre_dataset,
        )
        process_unzip_subcuenca(
            dataset=dataset,
            rutas_subcuencas=rutas_subcuencas,
            dir_data=dir_data
        )


def process_unzip_subcuenca(dataset: dict, rutas_subcuencas: dict, dir_data: str | Path) -> None:
    ## Descomprimir el archivo ZIP descargado en data/interim/inegi/.
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

    rutas_subcuencas[dataset["interim"]["key"]] = interim_dir / dir_data

    df = build_subcuencas_features(dataset["interim"]["key"],interim_dir / dir_data)

    #Crearemos un package por cada subcuenca
    for nombre_subcuenca, capas in df.items():

        processed_dir = Path(dataset["processed"]["directory"]) ##/ dataset["processed"]["filename"]
        processed_dir.mkdir(parents=True, exist_ok=True)

        print(f"Creando GeoPackage: {processed_dir} con las capas: {list(capas.keys())}")

        gpkg_dir = Path(dataset["processed"]["directory"]) / dataset["processed"]["filename"]
        # Si el GeoPackage ya existe, lo eliminamos
        if gpkg_dir.exists():
            gpkg_dir.unlink()

        # Creamos nuevamente el GeoPackage con las capas limpias
        for sufijo, df in capas.items():

            nombre_capa = sufijo.lstrip("_")

            df.to_file(
                gpkg_dir,
                layer=nombre_capa,
                driver="GPKG"
            )

def leer_capa(ruta_gpkg, nombre_capa):
    return gpd.read_file(
        ruta_gpkg,
        layer=nombre_capa
    )

if __name__ == "__main__":
    params = load_params()

    load_logging(
        level=params["logging"]["level"],
        log_file=Path(params["logging"]["file"]),
        console=params["logging"].get("console", False),
    )

    process_subcuencas(params)