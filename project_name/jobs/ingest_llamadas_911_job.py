from pathlib import Path

from project_name.clients.http import HttpClient
from project_name.config import load_dataset_config, load_logging, load_params
from project_name.logging import log_execution
from project_name.metadata.source import write_source_description
from project_name.policies.file import FilePolicy, OnExists


@log_execution
def ingest_llamadas_911(params: dict) -> None:
    dataset = load_dataset_config(params, source="llamadas911", dataset="llamadas_911")

    policy = FilePolicy(on_exists=OnExists(dataset["download"]["on_exists"]))

    destination = Path(dataset["raw"]["directory"]) / dataset["raw"]["filename"]

    HttpClient(file_policy=policy).download(
        url=dataset["url"],
        destination=destination,
    )

    write_source_description(
        source=params["sources"]["llamadas911"],
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

    ingest_llamadas_911(params)
