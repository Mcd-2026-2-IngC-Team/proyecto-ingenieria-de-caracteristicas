from pathlib import Path

from project_name.clients.http import HttpClient
from project_name.clients.inegi import InegiClient
from project_name.config import load_dataset_config, load_logging, load_params
from project_name.logging import log_execution
from project_name.metadata.source import write_source_description
from project_name.policies.file import FilePolicy, OnExists


@log_execution
def ingest_dcah(params: dict) -> None:
    dataset = load_dataset_config(
        params,
        source="inegi",
        dataset="dcah_2025",
    )

    policy = FilePolicy(on_exists=OnExists(dataset["download"]["on_exists"]))

    destination = Path(dataset["raw"]["directory"]) / dataset["raw"]["filename"]

    client = InegiClient(http_client=HttpClient(file_policy=policy))

    # El INEGI solo publica el paquete nacional (~556 MB) con un ZIP por estado
    # adentro; bajamos por rango únicamente el de Sonora (~15 MB).
    client.download_zip_member(
        url=dataset["url"],
        member=dataset["state_member"],
        destination=destination,
    )

    write_source_description(
        source=params["sources"]["inegi"],
        dataset=dataset,
        files=[destination],
        job=Path(__file__).stem,
        members=[dataset["state_member"]],
    )


if __name__ == "__main__":
    params = load_params()

    load_logging(
        level=params["logging"]["level"],
        log_file=Path(params["logging"]["file"]),
    )

    ingest_dcah(params)
