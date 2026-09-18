from concurrent.futures import ThreadPoolExecutor
import contextvars
from pathlib import Path

from project_name.clients.http import HttpClient
from project_name.clients.inegi import InegiClient
from project_name.config import load_dataset_config, load_logging, load_params
from project_name.logging import log_execution
from project_name.policies.file import FilePolicy, OnExists
from project_name.provenance import write_source_description


@log_execution
def ingest_mg_streets(params: dict) -> None:
    dataset = load_dataset_config(
        params,
        source="inegi",
        dataset="mg_2025_sonora",
    )

    policy = FilePolicy(on_exists=OnExists(dataset["download"]["on_exists"]))

    raw_dir = Path(dataset["raw"]["directory"])

    client = InegiClient(http_client=HttpClient(file_policy=policy))

    # Un shapefile son varios archivos (.shp, .shx, .dbf, .prj, .CPG); cada uno sale
    # por rango del paquete estatal (~73 MB), así que solo bajamos la capa de calles
    # y el metadato oficial. El servidor del INEGI limita la velocidad por conexión:
    # con un hilo por archivo la capa baja en ~8 s en vez de ~30 s.
    files = [raw_dir / Path(member).name for member in dataset["streets_members"]]
    with ThreadPoolExecutor(max_workers=len(files)) as pool:
        futures = [
            # Copia del contexto para que el log de cada hilo conserve el nombre del job.
            pool.submit(
                contextvars.copy_context().run,
                client.download_zip_member,
                url=dataset["url"],
                member=member,
                destination=destination,
            )
            for member, destination in zip(dataset["streets_members"], files)
        ]
    for future in futures:
        future.result()  # propaga el error de cualquier descarga

    write_source_description(
        source=params["sources"]["inegi"],
        dataset=dataset,
        files=files,
        job=Path(__file__).stem,
        members=dataset["streets_members"],
    )


if __name__ == "__main__":
    params = load_params()

    load_logging(
        level=params["logging"]["level"],
        log_file=Path(params["logging"]["file"]),
    )

    ingest_mg_streets(params)
