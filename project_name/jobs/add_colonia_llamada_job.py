from pathlib import Path

import pandas as pd

from project_name.config import load_dataset_config, load_logging, load_params
from project_name.constants import EXTERNAL_DIR
from project_name.logging import log_execution
from project_name.text import normalize_name

# La colonia del 911 es texto libre del operador: se empareja contra el
# catálogo INEGI por nombre normalizado (misma lógica que la libreta 07).
# Los nombres que no emparejan se resuelven con equivalencias_colonias_911.csv,
# un archivo de data/external revisado a mano: OK = nombre del catálogo
# correspondiente, vacío o "NA" = sin equivalencia definida.
EQUIVALENCIAS_FILE = EXTERNAL_DIR / "equivalencias_colonias_911.csv"


def load_llamadas_processed(dataset: dict) -> pd.DataFrame:
    input_file = Path(dataset["processed"]["directory"]) / dataset["processed"]["filename"]
    if not input_file.exists():
        raise FileNotFoundError(f"No se encontró el CSV procesado: {input_file}")
    df = pd.read_csv(input_file)
    # idempotente: si el job ya corrió, se recalcula desde cero
    return df.drop(columns=["colonia_id", "colonia_source"], errors="ignore")


def build_catalogo(colonias_csv: Path) -> pd.DataFrame:
    catalogo = pd.read_csv(
        colonias_csv,
        usecols=["colonia_id", "settlement_name"],
        dtype={"colonia_id": str},
    )
    catalogo["nombre_norm"] = catalogo["settlement_name"].map(normalize_name)
    catalogo["colonia_id"] = catalogo["colonia_id"].str.strip()
    # nombres repetidos con IDs distintos son ambiguos: no se asignan
    ids_por_nombre = catalogo.groupby("nombre_norm")["colonia_id"].nunique()
    ambiguos = set(ids_por_nombre[ids_por_nombre > 1].index)
    return (
        catalogo[~catalogo["nombre_norm"].isin(ambiguos)]
        .drop_duplicates("nombre_norm")[["nombre_norm", "colonia_id"]]
    )


def load_equivalencias(catalogo: pd.DataFrame) -> pd.Series:
    """lookup colonia_911 -> colonia_id usando el OK revisado a mano."""
    if not EQUIVALENCIAS_FILE.exists():
        raise FileNotFoundError(f"No se encontró {EQUIVALENCIAS_FILE}")
    eq = pd.read_csv(EQUIVALENCIAS_FILE)
    ok = eq[["colonia_911", "OK"]].dropna()
    ok = ok[ok["OK"].astype(str).str.strip().str.upper() != "NA"].copy()
    ok["nombre_norm"] = ok["OK"].map(normalize_name)
    resueltas = ok.merge(catalogo, on="nombre_norm", how="left")
    sin_resolver = resueltas[resueltas["colonia_id"].isna()]
    if len(sin_resolver):
        print(f"{len(sin_resolver)} equivalencias no están en el catálogo:")
        print(sin_resolver[["colonia_911", "OK"]].to_string(index=False))
    return resueltas.dropna(subset=["colonia_id"]).set_index("colonia_911")["colonia_id"]


@log_execution
def add_colonia_llamada(params: dict) -> None:
    llamadas_ds = load_dataset_config(
        params, source="llamadas911", dataset="llamadas_911_hermosillo"
    )
    colonias_ds = load_dataset_config(
        params, source="agua_hermosillo", dataset="colonias_hermosillo"
    )

    llamadas = load_llamadas_processed(llamadas_ds)
    catalogo = build_catalogo(
        Path(colonias_ds["processed"]["directory"]) / colonias_ds["processed"]["filename"]
    )

    llamadas["nombre_norm"] = llamadas["colonia"].map(normalize_name)
    llamadas = llamadas.merge(catalogo, on="nombre_norm", how="left")
    llamadas["colonia_source"] = llamadas["colonia_id"].notna().map(
        {True: "catalogo"}
    )

    lookup = load_equivalencias(catalogo)
    antes = llamadas["colonia_id"].isna()
    llamadas["colonia_id"] = llamadas["colonia_id"].fillna(
        llamadas["colonia"].map(lookup)
    )
    llamadas.loc[antes & llamadas["colonia_id"].notna(), "colonia_source"] = (
        "equivalencia"
    )

    llamadas = llamadas.drop(columns=["nombre_norm"])

    output_file = (
        Path(llamadas_ds["processed"]["directory"]) / llamadas_ds["processed"]["filename"]
    )
    llamadas.to_csv(output_file, index=False)

    recuperadas = int((antes & llamadas["colonia_id"].notna()).sum())
    print(
        f"{llamadas['colonia_id'].notna().sum()} / {len(llamadas)} llamadas con "
        f"colonia_id ({recuperadas} por equivalencias, "
        f"{int(llamadas['colonia_id'].isna().sum())} sin colonia) -> {output_file}"
    )


if __name__ == "__main__":
    params = load_params()
    load_logging(
        level=params["logging"]["level"],
        log_file=Path(params["logging"]["file"]),
        console=params["logging"].get("console", False),
    )
    add_colonia_llamada(params)
