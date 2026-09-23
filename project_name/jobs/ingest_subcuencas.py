from pathlib import Path

from project_name.clients.http import HttpClient
from project_name.clients.inegi import InegiClient
from project_name.config import load_dataset_config, load_logging, load_params
from project_name.logging import log_execution
from project_name.metadata.source import write_source_description
from project_name.policies.file import FilePolicy, OnExists


@log_execution
def ingest_subcuencas(params: dict) -> None:
# Ingestión de subcuencas de Sonora. Cada subcuenca se descarga de manera independiente en data/raw/inegi/. 
# Deben estar definidas en params.yml bajo sources.inegi.subcuencas.
    subcuencas = [
        "subc_la_manga",
        "subc_la_poza",
        "subc_r_son_hillo",
        "subc_r_san_miguel",
    ]

    for nombre_dataset in subcuencas:
        dataset = load_dataset_config(
            params,
            source="inegi",
            dataset=nombre_dataset,
        )

        ingest_subcuenca(
            params=params,
            dataset=dataset,
        )


def ingest_subcuenca(params: dict, dataset: dict) -> None:
    policy = FilePolicy(on_exists=OnExists(dataset["download"]["on_exists"]))

    destination = Path(dataset["raw"]["directory"]) / dataset["raw"]["filename"]

    client = InegiClient(http_client=HttpClient(file_policy=policy))

    client.download(
            url=dataset["url"],
            destination=destination,
    )

    write_source_description(
        source=params["sources"]["inegi"],
        dataset=dataset,
        files=[destination],
        job=Path(__file__).stem,
    )


if __name__ == "__main__":
    params = load_params()

    load_logging(
        level=params["logging"]["level"],
        log_file=Path(params["logging"]["file"]),
    )

    ingest_subcuencas(params)
