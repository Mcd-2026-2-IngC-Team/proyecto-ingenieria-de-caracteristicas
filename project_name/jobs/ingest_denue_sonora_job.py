from pathlib import Path
from typing import Dict

from project_name.clients.http import HttpClient
from project_name.config import load_dataset_config, load_logging, load_params
from project_name.logging import log_execution
from project_name.policies.file import FilePolicy, OnExists


@log_execution
def ingest_denue_sonora(params: Dict) -> None:
    params = load_params()

    load_logging(
        level=params["logging"]["level"],
        log_file=Path(params["logging"]["file"]),
    )

    dataset = load_dataset_config(
        params,
        source="inegi",
        dataset="denue_sonora_2024_05",
    )

    policy = FilePolicy(on_exists=OnExists(dataset["download"]["on_exists"]))

    destination = Path(dataset["raw"]["directory"]) / dataset["raw"]["filename"]

    client = HttpClient(file_policy=policy)

    client.download(
        url=dataset["url"],
        destination=destination,
    )


if __name__ == "__main__":
    params = load_params()

    load_logging(
        level=params["logging"]["level"],
        log_file=Path(params["logging"]["file"]),
    )

    ingest_denue_sonora(params)
