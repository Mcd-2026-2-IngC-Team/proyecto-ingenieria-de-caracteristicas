from pathlib import Path

from loguru import logger
import pandas as pd
import pandera.pandas as pa
import geopandas as gpd

from project_name.config import load_logging, load_params
from project_name.jobs.process_subcuencas_job import leer_capa
from project_name.logging import log_execution
from project_name.metadata.dictionary import DATE_COLUMNS, processed_files
from project_name.schemas import READ_DTYPES, SCHEMAS
from project_name.jobs.process_subcuencas_job import leer_capa,get_layer


def _log_failures(dataset: str, errors: pa.errors.SchemaErrors) -> None:
    # Una línea por regla rota, con cuántas filas la rompen y unos ejemplos.
    cases = errors.failure_cases
    for (column, check), group in cases.groupby(["column", "check"], dropna=False, sort=False):
        examples = group["failure_case"].drop_duplicates().head(5).tolist()
        logger.error(
            "{}: {} failed {} ({} rows), e.g. {}",
            dataset,
            column if pd.notna(column) else "<table>",
            check,
            len(group),
            examples,
        )


@log_execution
def validate_data(params: dict) -> None:
    failed = []
    for dataset, processed_file in processed_files(params).items():
        
        if not processed_file.exists():
            raise FileNotFoundError(f"{processed_file} not found: run `make data` first")

        if processed_file.suffix == ".gpkg":
            layers = gpd.list_layers(processed_file)["name"].tolist()

            for layer in layers:
                schema_dataset = f"{dataset}_{layer}"
                logger.info("schema_dataset: {}", schema_dataset)
                schema = SCHEMAS.get(schema_dataset)

                if schema is None:
                    logger.info(
                        "Validating {}",
                        schema_dataset,
                    )

                df = leer_capa(processed_file, layer)

                try:
                    schema.validate(df, lazy=True)
                except pa.errors.SchemaErrors as errors:
                    _log_failures(schema_dataset, errors)
                    failed.append(schema_dataset)
                    continue
                    
                logger.info(
                    "{}: {} rows pass the quality rules",
                    schema_dataset,
                    len(df),
                )
    
        else:
            schema = SCHEMAS.get(dataset)
            if schema is None:
                logger.info("No quality rules for {}, skipped", dataset)
                continue
            
            df = pd.read_csv(
                processed_file,
                parse_dates=DATE_COLUMNS.get(dataset, []),
                dtype=READ_DTYPES.get(dataset),
            )

        try:
            # lazy=True junta todas las reglas rotas en vez de parar en la primera.
            schema.validate(df, lazy=True)
        except pa.errors.SchemaErrors as errors:
            _log_failures(dataset, errors)
            failed.append(dataset)
            continue
        logger.info("{}: {} rows pass the quality rules", dataset, len(df))

    if failed:
        raise ValueError(f"Quality rules failed for: {', '.join(failed)} (see the log)")


if __name__ == "__main__":
    params = load_params()

    load_logging(
        level=params["logging"]["level"],
        log_file=Path(params["logging"]["file"]),
        console=params["logging"].get("console", False),
    )

    validate_data(params)
