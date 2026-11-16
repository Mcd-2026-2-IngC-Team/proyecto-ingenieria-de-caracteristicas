from pathlib import Path
from urllib.parse import urlencode

from project_name.clients.http import HttpClient
from project_name.config import load_dataset_config, load_logging, load_params
from project_name.logging import log_execution
from project_name.metadata.source import write_source_description
from project_name.policies.file import FilePolicy, OnExists


def build_archive_url(dataset: dict) -> str:
    # La API responde todo el rango en una sola petición JSON; los parámetros viven
    # en params.yml para que el periodo y el punto queden documentados.
    return f"{dataset['url']}?{urlencode(dataset['query'])}"


@log_execution
def ingest_precipitacion(params: dict) -> None:
    dataset = load_dataset_config(params, source="open_meteo", dataset="precipitacion_hermosillo")

    policy = FilePolicy(on_exists=OnExists(dataset["download"]["on_exists"]))

    destination = Path(dataset["raw"]["directory"]) / dataset["raw"]["filename"]

    HttpClient(file_policy=policy).download(
        url=build_archive_url(dataset),
        destination=destination,
    )

    write_source_description(
        source=params["sources"]["open_meteo"],
        dataset=dataset,
        files=[destination],
        job=Path(__file__).stem,
    )


if __name__ == "__main__":
    params = load_params()

    load_logging(
        level=params["logging"]["level"],
        log_file=Path(params["logging"]["file"]),
        console=params["logging"].get("console", False),
    )

    ingest_precipitacion(params)
