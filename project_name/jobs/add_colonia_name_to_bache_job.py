import ast
from pathlib import Path

import pandas as pd


# ============================================================
# Configuración
# ============================================================

PROJECT_ROOT = Path(__file__).resolve().parents[2]

BACHES_CSV = Path("data/processed/bachometro/baches_hermosillo.csv")
COLONIAS_CSV = Path("data/processed/bachometro/relacion_colonia_baches_id.csv")
OUTPUT_CSV = Path("data/processed/bachometro/baches_hermosillo_con_colonias.csv")



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

def get_colonias(neighborhoods, colonia_lookup):
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

        colonia = colonia_lookup.get(neighborhood_id)

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

    print(f"Leyendo baches: {BACHES_CSV}")
    print(f"Leyendo relación de colonias: {COLONIAS_CSV}")

    # --------------------------------------------------------
    # Leer archivos
    # --------------------------------------------------------

    baches_df = pd.read_csv(BACHES_CSV)
    colonias_df = pd.read_csv(COLONIAS_CSV)

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
        colonias_df["neighborhood_id"].astype(int)
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
        f"Colonias disponibles: {len(colonia_lookup)}"
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

    sin_colonia = total - con_colonia

    print()
    print(f"Total de baches: {total}")
    print(f"Baches con colonia: {con_colonia}")
    print(f"Baches sin colonia: {sin_colonia}")

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
    print(f"Archivo generado: {OUTPUT_CSV}")


# ============================================================
# Entry point
# ============================================================

if __name__ == "__main__":
    main()