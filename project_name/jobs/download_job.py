from concurrent.futures import ThreadPoolExecutor
import contextvars
from pathlib import Path

from project_name.config import load_logging, load_params
from project_name.jobs.ingest_dcah_job import ingest_dcah
from project_name.jobs.ingest_denue_sonora_job import ingest_denue_sonora
from project_name.jobs.ingest_mg_streets_job import ingest_mg_streets
from project_name.jobs.ingest_baches_job import ingest_bachometro
from project_name.jobs.ingest_subc_la_poza import ingest_subc_la_poza
from project_name.jobs.ingest_subc_r_son_hillo import ingest_subc_r_son_hillo 
from project_name.jobs.ingest_subc_la_manga import ingest_subc_la_manga
from project_name.jobs.ingest_subc_r_san_miguel import ingest_subc_r_san_miguel
from project_name.logging import log_execution

INGEST_JOBS = (
    ingest_denue_sonora, 
    ingest_dcah, 
    ingest_mg_streets, 
    ingest_bachometro, 
    ingest_subc_la_poza, 
    ingest_subc_r_son_hillo, 
    ingest_subc_la_manga,
    ingest_subc_r_san_miguel
)


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
