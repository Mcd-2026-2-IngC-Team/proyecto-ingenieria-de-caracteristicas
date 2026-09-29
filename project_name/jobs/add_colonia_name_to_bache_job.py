import ast
from pathlib import Path

import pandas as pd
import requests

from project_name.config import load_dataset_config, load_params


# ============================================================
# Configuración SharePoint
# ============================================================

SHAREPOINT_URL = (
    "https://unisonmx-my.sharepoint.com/:x:/g/personal/"
    "a211205228_unison_mx/"
    "IQACmnNydZIQQI5JGpGa4eJhAZY4udk_M0NHsuOkZEuTV8o"
    "?e=i21kCd&download=1"
)


# ============================================================
# Descargar archivo de colonias
# ============================================================

def download_colonias(
    url: str,
    output_path: Path,
) -> Path:
    """
    Descarga el archivo de relación colonia/neighborhood
    desde SharePoint.

    Devuelve el Path del archivo descargado.
    """

    output_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    print(f"Descargando colonias desde SharePoint...")

    response = requests.get(
        url,
        timeout=60,
        allow_redirects=True,
    )

    response.raise_for_status()

    output_path.write_bytes(response.content)

    print(f"Archivo descargado: {output_path}")

    return output_path


# ============================================================
# Parsear neighborhoods
# ============================================================

def parse_neighborhoods(value):
    """
    Convierte el campo neighborhoods en una lista de IDs.

    Ejemplos:

        "[12, 22]" -> [12, 22]
        "[35]"     -> [35]
        "[]"       -> []
        NaN        -> []
    """

    if pd.isna(value):
        return []

    if isinstance(value, list):
        return value

    if isinstance(value, str):
        try:
            parsed = ast.literal_eval(value)

            if isinstance(parsed, list):
                return parsed

            return [parsed]

        except (ValueError, SyntaxError):
            print(
                f"No se pudo interpretar neighborhoods: {value}"
            )
            return []

    return [value]


# ============================================================
# Obtener colonias
# ============================================================

def get_colonias(
    neighborhoods,
    colonia_lookup,
):
    """
    Obtiene las colonias correspondientes a los IDs
    contenidos en neighborhoods.

    Ejemplo:

        [12, 22]

    con:

        12 -> Centro
        22 -> San Benito

    devuelve:

        "Centro, San Benito"
    """

    colonias = []

    for neighborhood_id in neighborhoods:

        try:
            neighborhood_id = int(neighborhood_id)

        except (ValueError, TypeError):
            continue

        colonia = colonia_lookup.get(
            neighborhood_id
        )

        # Ignorar IDs que no tengan colonia
        if colonia is None or pd.isna(colonia):
            continue

        colonia = str(colonia).strip()

        if not colonia:
            continue

        # Evitar colonias repetidas
        if colonia not in colonias:
            colonias.append(colonia)

    return ", ".join(colonias)


# ============================================================
# Job principal
# ============================================================

def main():

    # --------------------------------------------------------
    # Cargar configuración CCDS
    # --------------------------------------------------------

    params = load_params()

    dataset = load_dataset_config(
        params,
        source="bachometro",
        dataset="baches",
    )

    raw_directory = Path(
        dataset["raw"]["directory"]
    )

    processed_directory = Path(
        dataset["processed"]["directory"]
    )

    # --------------------------------------------------------
    # Definir archivos
    # --------------------------------------------------------

    BACHES_CSV = (
        processed_directory
        / "baches_hermosillo.csv"
    )

    COLONIAS_CSV = (
        raw_directory
        / "relacion_colonia_baches_id.csv"
    )

    OUTPUT_CSV = (
        processed_directory
        / "baches_hermosillo_con_colonias.csv"
    )

    # --------------------------------------------------------
    # Descargar archivo de colonias desde SharePoint
    # --------------------------------------------------------

    colonias_csv = download_colonias(
        SHAREPOINT_URL,
        COLONIAS_CSV,
    )

    # --------------------------------------------------------
    # Leer archivos
    # --------------------------------------------------------

    print()
    print(f"Leyendo baches: {BACHES_CSV}")
    print(
        f"Leyendo relación de colonias: "
        f"{colonias_csv}"
    )

    baches_df = pd.read_csv(
        BACHES_CSV
    )

    colonias_df = pd.read_csv(
        colonias_csv
    )

    # --------------------------------------------------------
    # Validaciones
    # --------------------------------------------------------

    if "neighborhoods" not in baches_df.columns:
        raise ValueError(
            "baches_hermosillo.csv no contiene "
            "la columna 'neighborhoods'."
        )

    if "neighborhood_id" not in colonias_df.columns:
        raise ValueError(
            "relacion_colonia_baches_id.csv no contiene "
            "la columna 'neighborhood_id'."
        )

    if "colonia" not in colonias_df.columns:
        raise ValueError(
            "relacion_colonia_baches_id.csv no contiene "
            "la columna 'colonia'."
        )

    # --------------------------------------------------------
    # Limpiar IDs
    # --------------------------------------------------------

    colonias_df["neighborhood_id"] = pd.to_numeric(
        colonias_df["neighborhood_id"],
        errors="coerce",
    )

    colonias_df = colonias_df.dropna(
        subset=["neighborhood_id"]
    )

    colonias_df["neighborhood_id"] = (
        colonias_df["neighborhood_id"]
        .astype(int)
    )

    # --------------------------------------------------------
    # Crear lookup
    #
    # {
    #     12: "Centro",
    #     22: "San Benito",
    #     35: "Las Quintas"
    # }
    # --------------------------------------------------------

    colonia_lookup = (
        colonias_df
        .set_index("neighborhood_id")["colonia"]
        .to_dict()
    )

    print(
        f"Colonias disponibles: "
        f"{len(colonia_lookup)}"
    )

    # --------------------------------------------------------
    # Parsear neighborhoods
    # --------------------------------------------------------

    neighborhoods_parsed = (
        baches_df["neighborhoods"]
        .apply(parse_neighborhoods)
    )

    # --------------------------------------------------------
    # Crear columna colonia
    # --------------------------------------------------------

    baches_df["colonia"] = (
        neighborhoods_parsed
        .apply(
            lambda ids: get_colonias(
                ids,
                colonia_lookup,
            )
        )
    )

    # --------------------------------------------------------
    # Estadísticas
    # --------------------------------------------------------

    total = len(baches_df)

    con_colonia = (
        baches_df["colonia"]
        .ne("")
        .sum()
    )

    sin_colonia = (
        total - con_colonia
    )

    print()
    print(f"Total de baches: {total}")
    print(
        f"Baches con colonia: "
        f"{con_colonia}"
    )
    print(
        f"Baches sin colonia: "
        f"{sin_colonia}"
    )

    # --------------------------------------------------------
    # Guardar resultado
    # --------------------------------------------------------

    OUTPUT_CSV.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    baches_df.to_csv(
        OUTPUT_CSV,
        index=False,
        encoding="utf-8",
    )

    print()
    print(
        f"Archivo generado: "
        f"{OUTPUT_CSV}"
    )


# ============================================================
# Entry point
# ============================================================

if __name__ == "__main__":
    main()