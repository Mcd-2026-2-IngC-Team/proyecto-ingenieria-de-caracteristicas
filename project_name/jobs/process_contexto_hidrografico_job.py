from pathlib import Path

import geopandas as gpd

from project_name.config import load_dataset_config, load_logging, load_params
from project_name.hydro_context import hydro_context
from project_name.logging import log_execution

CITY_LOCALITY = "0001"


@log_execution
def process_contexto_hidrografico(params: dict) -> None:
    subc = load_dataset_config(params, source="inegi", dataset="subc_hermosillo")
    colonias_ds = load_dataset_config(
        params, source="agua_hermosillo", dataset="colonias_hermosillo"
    )
    dataset = load_dataset_config(params, source="inegi", dataset="colonias_contexto_hidrografico")

    streams_file = Path(subc["processed"]["directory"]) / subc["processed"]["filename"]
    # El GeoPackage de colonias lo escribe process_colonias_hermosillo_job junto al CSV.
    colonias_file = (
        Path(colonias_ds["processed"]["directory"]) / colonias_ds["processed"]["filename"]
    ).with_suffix(".gpkg")
    for required in (streams_file, colonias_file):
        if not required.exists():
            raise FileNotFoundError(f"{required} not found: run `make data` first")

    colonias = gpd.read_file(colonias_file)
    colonias = colonias[colonias["locality_code"] == CITY_LOCALITY].reset_index(drop=True)
    streams = gpd.read_file(streams_file, layer="hl")

    contexts = hydro_context(colonias, streams)
    print(contexts["context_name"].value_counts().sort_index().to_string())

    output = Path(dataset["processed"]["directory"]) / dataset["processed"]["filename"]
    output.parent.mkdir(parents=True, exist_ok=True)
    contexts.to_csv(output, index=False)


if __name__ == "__main__":
    params = load_params()

    load_logging(
        level=params["logging"]["level"],
        log_file=Path(params["logging"]["file"]),
        console=params["logging"].get("console", False),
    )

    process_contexto_hidrografico(params)
