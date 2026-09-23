from pathlib import Path
from datetime import datetime

from project_name.clients.bachometro import BachometroClient
from project_name.clients.http import HttpClient
from project_name.config import load_dataset_config, load_logging, load_params
from project_name.logging import log_execution
from project_name.policies.file import FilePolicy, OnExists
from project_name.metadata.source import write_source_description

current_year = datetime.now().year

@log_execution
def ingest_bachometro(params: dict) -> None:
    dataset = load_dataset_config(
        params,
        source="bachometro",
        dataset="baches",
    )

    downloaded_files = []

    for year in dataset["years"]:
        on_exists = (
            # Hacemos revisión del año actual pues este dataset
            # sí se sigue actualizando y hay que sobreescribirlo
            # Los años anteriores ya sn información definida
            OnExists.OVERWRITE
            if year == current_year
            else OnExists(dataset["download"]["on_exists"])
        )

        policy = FilePolicy(on_exists=on_exists)

        client = BachometroClient(
            http_client=HttpClient(file_policy=policy)
        )

        destination = (
            Path(dataset["raw"]["directory"])
            / dataset["raw"]["filename"].format(year=year)
        )

        client.download_year(
            url=dataset["url"],
            year=year,
            destination=destination,
        )

        downloaded_files.append(destination)

    write_source_description(
        source=params["sources"]["bachometro"],
        dataset=dataset,
        files=downloaded_files,
        job=Path(__file__).stem,
    )


if __name__ == "__main__":
    params = load_params()

    load_logging(
        level=params["logging"]["level"],
        log_file=Path(params["logging"]["file"]),
        console=params["logging"].get("console", False),
    )

    ingest_bachometro(params)