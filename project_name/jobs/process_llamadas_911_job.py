from pathlib import Path

from project_name.config import load_dataset_config, load_logging, load_params
from project_name.features import clean_llamadas_911, load_llamadas_911
from project_name.logging import log_execution

# El catálogo de TIPO DE INCIDENTE del 911 tiene valores duplicados por
# ortografía: un mismo concepto fue capturado como dos cadenas distintas.
# Ambos valores pasan el filtro de GRUPOS_INCIDENTE_911 y aquí se unifican
# al valor mayoritario del catálogo:
#   "ÁRBOL CAÍDO O POR CAER" (45 llamadas) -> "ARBOL CAÍDO O POR CAER" (1,723)
#   "VIALIDAD EN MAL ESTADO-BACHES" (28)   -> "VIALIDAD EN MAL ESTADO" (221)
# Resultado: 34 valores del catálogo quedan en 32 tipos canónicos.
TIPOS_INCIDENTE_EQUIVALENTES = {
    "ÁRBOL CAÍDO O POR CAER": "ARBOL CAÍDO O POR CAER",
    "VIALIDAD EN MAL ESTADO-BACHES": "VIALIDAD EN MAL ESTADO",
}


@log_execution
def process_llamadas_911(params: dict) -> None:
    dataset = load_dataset_config(
        params,
        source="llamadas911",
        dataset="llamadas_911_hermosillo",
    )

    input_file = Path(dataset["raw"]["directory"]) / dataset["raw"]["filename"]

    processed_directory = Path(dataset["processed"]["directory"])
    output_file = processed_directory / dataset["processed"]["filename"]

    if not input_file.exists():
        raise FileNotFoundError(f"No se encontró el archivo de llamadas 911: {input_file}")

    df = load_llamadas_911(input_file)
    print(f"{len(df)} llamadas crudas")

    df = clean_llamadas_911(df)
    df["tipo_incidente"] = df["tipo_incidente"].replace(TIPOS_INCIDENTE_EQUIVALENTES)
    print(f"{len(df)} llamadas con tipo de incidente seleccionado, sin nulos")
    print(df["grupo_incidente"].value_counts().to_string())

    processed_directory.mkdir(parents=True, exist_ok=True)
    df.to_csv(output_file, index=False)


if __name__ == "__main__":
    params = load_params()

    load_logging(
        level=params["logging"]["level"],
        log_file=Path(params["logging"]["file"]),
        console=params["logging"].get("console", False),
    )

    process_llamadas_911(params)
