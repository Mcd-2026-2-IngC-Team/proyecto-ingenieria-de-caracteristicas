from concurrent.futures import ThreadPoolExecutor
import contextvars
from pathlib import Path

from project_name.config import load_logging, load_params
from project_name.jobs.ingest_dcah_job import ingest_dcah
from project_name.jobs.ingest_denue_sonora_job import ingest_denue_sonora
from project_name.jobs.ingest_mg_streets_job import ingest_mg_streets
from project_name.logging import log_execution

INGEST_JOBS = (ingest_denue_sonora, ingest_dcah, ingest_mg_streets)


@log_execution
def download(params: dict) -> None:
    # Las fuentes son independientes (cada una con su carpeta en data/raw) y el
    # servidor del INEGI limita la velocidad por conexión, así que las bajamos a la vez.
    with ThreadPoolExecutor(max_workers=len(INGEST_JOBS)) as pool:
        futures = [pool.submit(contextvars.copy_context().run, job, params) for job in INGEST_JOBS]
    for future in futures:
        future.result()  # propaga el error de cualquier fuente


if __name__ == "__main__":
    params = load_params()

    load_logging(
        level=params["logging"]["level"],
        log_file=Path(params["logging"]["file"]),
    )

    download(params)
