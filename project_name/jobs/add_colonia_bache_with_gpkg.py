import unicodedata
from pathlib import Path

import fiona
import geopandas as gpd
import pandas as pd

from project_name.config import load_dataset_config, load_params


# ============================================================
# Configuración espacial
# ============================================================

# CRS métrico usado para calcular distancias en metros.
METRIC_CRS = "EPSG:6372"

# Solo se usa para puntos que NO caen dentro de ningún polígono.
# Ajusta este valor después de revisar la distribución de distancias.
MAX_NEAREST_DISTANCE_M = 500.0

# Umbral para detectar puntos alejados de cualquier asentamiento.
# Si el asentamiento más cercano está a más de esta distancia,
# se marca como probable carretera/zona rural.
DISTANCE_TO_SETTLEMENT_M = 1000.0


# ============================================================
# Funciones auxiliares
# ============================================================


def normalize_name(value):
    """Normaliza nombres de colonias para comparación."""
    if pd.isna(value):
        return pd.NA

    value = str(value).strip().upper()
    value = unicodedata.normalize("NFKD", value)
    value = "".join(
        char for char in value if not unicodedata.combining(char)
    )
    value = " ".join(value.split())

    return value if value else pd.NA


# ============================================================
# Configuración
# ============================================================

params = load_params()

colonias_ds = load_dataset_config(
    params,
    source="agua_hermosillo",
    dataset="colonias_hermosillo",
)

baches_ds = load_dataset_config(
    params,
    source="bachometro",
    dataset="baches",
)


# ============================================================
# Paths
# ============================================================

colonias_processed_directory = Path(
    colonias_ds["processed"]["directory"]
)

baches_processed_directory = Path(
    baches_ds["processed"]["directory"]
)

GPKG_PATH = (
    colonias_processed_directory
    / "colonias_hermosillo.gpkg"
)

BACHES_PATH = (
    baches_processed_directory
    / "baches_hermosillo_con_colonias.csv"
)


# ============================================================
# Validar existencia de archivos
# ============================================================

if not GPKG_PATH.exists():
    raise FileNotFoundError(
        f"No se encontró el GPKG: {GPKG_PATH}"
    )

if not BACHES_PATH.exists():
    raise FileNotFoundError(
        f"No se encontró el CSV de baches: {BACHES_PATH}"
    )


# ============================================================
# Cargar GPKG
# ============================================================

layers = fiona.listlayers(GPKG_PATH)
print("\n--- Layers GPKG ---")
print(layers)

if "colonias_hermosillo" not in layers:
    raise ValueError(
        "No existe la layer 'colonias_hermosillo' en el GPKG."
    )

colonias = gpd.read_file(
    GPKG_PATH,
    layer="colonias_hermosillo",
)

print("\n--- GPKG ---")
print("Shape:", colonias.shape)
print("CRS:", colonias.crs)
print("Columnas:", colonias.columns.tolist())
print("\nTipos de geometría:")
print(colonias.geometry.geom_type.value_counts())
print("\nGeometrías inválidas:")
print((~colonias.geometry.is_valid).sum())
print("\nGeometrías vacías:")
print(colonias.geometry.is_empty.sum())
print("\nGeometrías nulas:")
print(colonias.geometry.isna().sum())

if colonias.geometry.isna().any():
    raise ValueError("Existen geometrías nulas en colonias.")

if (~colonias.geometry.is_valid).any():
    raise ValueError("Existen geometrías inválidas en colonias.")


# ============================================================
# Cargar baches
# ============================================================

baches = pd.read_csv(BACHES_PATH)

print("\n--- Baches ---")
print("Shape:", baches.shape)
print("Columnas:", baches.columns.tolist())

required_baches_columns = {
    "latitude",
    "longitude",
    "colonia",
}

missing_columns = required_baches_columns - set(baches.columns)
if missing_columns:
    raise ValueError(
        "Faltan columnas necesarias en baches: "
        f"{missing_columns}"
    )

required_colonias_columns = {
    "colonia_id",
    "settlement_name",
    "settlement_name_normalized",
    "settlement_type",
    "geometry",
}

missing_columns = required_colonias_columns - set(colonias.columns)
if missing_columns:
    raise ValueError(
        "Faltan columnas necesarias en GPKG: "
        f"{missing_columns}"
    )


# ============================================================
# Limpiar colonia original
# ============================================================

baches["colonia"] = (
    baches["colonia"]
    .replace(r"^\s*$", pd.NA, regex=True)
)

print(
    "\nBaches sin colonia original:",
    baches["colonia"].isna().sum(),
)

print(
    "Baches sin latitude:",
    baches["latitude"].isna().sum(),
)

print(
    "Baches sin longitude:",
    baches["longitude"].isna().sum(),
)


# ============================================================
# Convertir baches a GeoDataFrame
# ============================================================

baches_geo = gpd.GeoDataFrame(
    baches.copy(),
    geometry=gpd.points_from_xy(
        baches["longitude"],
        baches["latitude"],
    ),
    crs="EPSG:4326",
)

if baches_geo.crs != colonias.crs:
    print(
        "\nTransformando CRS:",
        baches_geo.crs,
        "->",
        colonias.crs,
    )
    baches_geo = baches_geo.to_crs(colonias.crs)


# ============================================================
# Seleccionar columnas necesarias del GPKG
# ============================================================

colonias_join = colonias[
    [
        "colonia_id",
        "settlement_name",
        "settlement_name_normalized",
        "settlement_type",
        "geometry",
    ]
].copy()


# ============================================================
# PASO 1: Spatial join exacto (within)
# ============================================================

# Primero intentamos determinar la colonia de forma exacta:
# el punto debe estar dentro del polígono.
baches_joined = gpd.sjoin(
    baches_geo,
    colonias_join,
    how="left",
    predicate="within",
)

print("\n--- Spatial Join: within ---")
print("Baches originales:", len(baches))
print("Baches después del join:", len(baches_joined))

if len(baches_joined) != len(baches):
    print(
        "\nADVERTENCIA: el spatial join cambió el número "
        "de registros. Esto puede indicar polígonos superpuestos."
    )

# Auditoría del método espacial.
baches_joined["spatial_match_method"] = pd.NA
baches_joined["distance_to_colonia_m"] = pd.NA

within_mask = baches_joined["settlement_name"].notna()

baches_joined.loc[
    within_mask,
    "spatial_match_method",
] = "within"

baches_joined.loc[
    within_mask,
    "distance_to_colonia_m",
] = 0.0

print(
    "Encontrados con within:",
    int(within_mask.sum()),
)
print(
    "Fuera de polígonos después de within:",
    int((~within_mask).sum()),
)


# ============================================================
# PASO 2: Distancia a la colonia/asentamiento más cercano
# ============================================================

# Para los puntos que NO quedaron dentro de ningún polígono:
# 1. Calculamos la distancia real al asentamiento más cercano.
# 2. Si está <= MAX_NEAREST_DISTANCE_M, usamos esa colonia como
#    fallback para huecos de calles/avenidas.
# 3. Si está > DISTANCE_TO_SETTLEMENT_M, NO asignamos colonia y
#    lo marcamos como probable carretera/zona rural.

baches_joined["fuera_asentamiento"] = pd.NA
baches_joined["contexto_ubicacion"] = pd.NA

# Los puntos dentro de una colonia ya tienen distance_to_colonia_m = 0.
baches_joined.loc[within_mask, "fuera_asentamiento"] = False
baches_joined.loc[within_mask, "contexto_ubicacion"] = "dentro_asentamiento"

unmatched_indices = baches_joined.index[
    baches_joined["settlement_name"].isna()
].unique()

if len(unmatched_indices) > 0:
    baches_missing = baches_geo.loc[
        baches_geo.index.intersection(unmatched_indices),
        ["geometry"],
    ].copy()

    baches_missing_metric = baches_missing.to_crs(METRIC_CRS)
    colonias_metric = colonias_join.to_crs(METRIC_CRS)

    # Sin max_distance: necesitamos conocer la distancia real
    # al asentamiento más cercano para clasificar el contexto.
    nearest = gpd.sjoin_nearest(
        baches_missing_metric,
        colonias_metric,
        how="left",
        distance_col="distance_to_colonia_m",
    )

    # Puede haber empates exactos. Conservamos una fila por punto.
    nearest = (
        nearest
        .sort_values(
            "distance_to_colonia_m",
            na_position="last",
        )
        .loc[lambda df: ~df.index.duplicated(keep="first")]
    )

    # Para todos los puntos fuera de polígonos, guardar la distancia
    # real al polígono de colonia más cercano, aunque esté demasiado
    # lejos para asignarle una colonia.
    baches_joined.loc[
        nearest.index,
        "distance_to_colonia_m",
    ] = nearest["distance_to_colonia_m"]

    # --------------------------------------------------------
    # 2A. Asignar colonia solo si está suficientemente cerca
    # --------------------------------------------------------
    nearest_assign_mask = (
        nearest["settlement_name"].notna()
        & nearest["distance_to_colonia_m"].le(
            MAX_NEAREST_DISTANCE_M
        )
    )

    nearest_matched = nearest.loc[nearest_assign_mask].copy()

    columns_to_fill = [
        "colonia_id",
        "settlement_name",
        "settlement_name_normalized",
        "settlement_type",
    ]

    for column in columns_to_fill:
        baches_joined.loc[nearest_matched.index, column] = (
            nearest_matched[column]
        )

    baches_joined.loc[
        nearest_matched.index,
        "spatial_match_method",
    ] = "nearest"

    # --------------------------------------------------------
    # 2B. Clasificar contexto según distancia a asentamiento
    # --------------------------------------------------------
    near_settlement_mask = (
        nearest["distance_to_colonia_m"].notna()
        & nearest["distance_to_colonia_m"].le(
            DISTANCE_TO_SETTLEMENT_M
        )
    )
    near_settlement_indices = nearest.index[near_settlement_mask]

    baches_joined.loc[
        near_settlement_indices,
        "fuera_asentamiento",
    ] = False
    baches_joined.loc[
        near_settlement_indices,
        "contexto_ubicacion",
    ] = "cerca_asentamiento"

    outside_mask = (
        nearest["distance_to_colonia_m"].notna()
        & nearest["distance_to_colonia_m"].gt(
            DISTANCE_TO_SETTLEMENT_M
        )
    )
    outside_indices = nearest.index[outside_mask]

    baches_joined.loc[
        outside_indices,
        "fuera_asentamiento",
    ] = True
    baches_joined.loc[
        outside_indices,
        "contexto_ubicacion",
    ] = "probable_carretera_o_zona_rural"

    print("\n--- Fallback / distancia a asentamiento ---")
    print(
        "Máxima distancia para asignar colonia (m):",
        MAX_NEAREST_DISTANCE_M,
    )
    print(
        "Umbral fuera de asentamiento (m):",
        DISTANCE_TO_SETTLEMENT_M,
    )
    print("Puntos evaluados:", len(nearest))
    print("Puntos recuperados con nearest:", len(nearest_matched))
    print(
        "Puntos a más del umbral de cualquier asentamiento:",
        int(outside_mask.sum()),
    )

    valid_distances = nearest[
        "distance_to_colonia_m"
    ].dropna()

    if not valid_distances.empty:
        print("\nDistribución de distancia al asentamiento más cercano (m):")
        print(
            valid_distances.describe(
                percentiles=[0.50, 0.75, 0.90, 0.95, 0.99]
            )
        )

baches_joined["fuera_asentamiento"] = (
    baches_joined["fuera_asentamiento"].astype("boolean")
)


# ============================================================
# Renombrar y normalizar colonia original
# ============================================================

baches_joined = baches_joined.rename(
    columns={"colonia": "colonia_original"}
)

baches_joined["colonia_original"] = (
    baches_joined["colonia_original"]
    .replace(r"^\s*$", pd.NA, regex=True)
)

baches_joined["settlement_name"] = (
    baches_joined["settlement_name"]
    .replace(r"^\s*$", pd.NA, regex=True)
)

# Normalizamos AMBOS lados con exactamente la misma función.
baches_joined["colonia_original_normalized"] = (
    baches_joined["colonia_original"]
    .apply(normalize_name)
)

baches_joined["settlement_name_normalized"] = (
    baches_joined["settlement_name"]
    .apply(normalize_name)
)


# ============================================================
# Comparar colonia original vs colonia espacial
# ============================================================

both_present = (
    baches_joined["colonia_original_normalized"].notna()
    & baches_joined["settlement_name_normalized"].notna()
)

baches_joined["colonia_match"] = pd.NA

baches_joined.loc[
    both_present,
    "colonia_match",
] = (
    baches_joined.loc[
        both_present,
        "colonia_original_normalized",
    ]
    == baches_joined.loc[
        both_present,
        "settlement_name_normalized",
    ]
)

baches_joined["colonia_match"] = (
    baches_joined["colonia_match"]
    .astype("boolean")
)


# ============================================================
# Crear colonia final
# ============================================================

# Prioridad:
# 1. colonia_original
# 2. settlement_name obtenido espacialmente
baches_joined["colonia"] = (
    baches_joined["colonia_original"]
    .fillna(baches_joined["settlement_name"])
)


# ============================================================
# Fuente de colonia final
# ============================================================

baches_joined["colonia_source"] = pd.NA

baches_joined.loc[
    baches_joined["colonia_original"].notna(),
    "colonia_source",
] = "original"

# Si faltaba colonia original, diferenciamos si el valor espacial
# vino de within o del fallback nearest.
for method in ["within", "nearest"]:
    mask = (
        baches_joined["colonia_original"].isna()
        & baches_joined["settlement_name"].notna()
        & baches_joined["spatial_match_method"].eq(method)
    )

    baches_joined.loc[
        mask,
        "colonia_source",
    ] = f"spatial_{method}"


# ============================================================
# Fallback final: usar contexto de ubicación como colonia
# ============================================================

# Si después de colonia_original + spatial within + spatial nearest
# el registro sigue sin colonia, usamos el contexto espacial.
#
# Ejemplos:
#   cerca_asentamiento
#   probable_carretera_o_zona_rural
#
# Esto evita dejar colonia en NA cuando sí tenemos información útil
# sobre el tipo de ubicación.

contexto_fallback_mask = (
    baches_joined["colonia"].isna()
    & baches_joined["contexto_ubicacion"].notna()
)

baches_joined.loc[
    contexto_fallback_mask,
    "colonia",
] = baches_joined.loc[
    contexto_fallback_mask,
    "contexto_ubicacion",
]

baches_joined.loc[
    contexto_fallback_mask,
    "colonia_source",
] = "contexto_ubicacion"


# ============================================================
# Estadísticas finales
# ============================================================

print("\n--- Resultado ---")
print(
    "Sin colonia original:",
    baches_joined["colonia_original"].isna().sum(),
)
print(
    "Sin settlement_name después de within + nearest:",
    baches_joined["settlement_name"].isna().sum(),
)
print(
    "Sin colonia final:",
    baches_joined["colonia"].isna().sum(),
)

print("\n--- spatial_match_method ---")
print(
    baches_joined["spatial_match_method"]
    .value_counts(dropna=False)
)

print("\n--- colonia_match ---")
print(
    baches_joined["colonia_match"]
    .value_counts(dropna=False)
)

print("\n--- colonia_source ---")
print(
    baches_joined["colonia_source"]
    .value_counts(dropna=False)
)


# ============================================================
# Mostrar discrepancias
# ============================================================

discrepancias = baches_joined[
    baches_joined["colonia_match"].eq(False)
]

print("\nDiscrepancias:", len(discrepancias))
print(
    discrepancias[
        [
            "id_row",
            "latitude",
            "longitude",
            "colonia_original",
            "colonia_original_normalized",
            "settlement_name",
            "settlement_name_normalized",
            "spatial_match_method",
            "distance_to_colonia_m",
            "colonia_match",
        ]
    ].head(50)
)


# ============================================================
# Mostrar puntos recuperados por nearest
# ============================================================

nearest_rows = baches_joined[
    baches_joined["spatial_match_method"].eq("nearest")
]

print(
    "\nBaches asignados mediante nearest:",
    len(nearest_rows),
)

print(
    nearest_rows[
        [
            "id_row",
            "latitude",
            "longitude",
            "colonia_original",
            "settlement_name",
            "distance_to_colonia_m",
            "colonia",
        ]
    ].head(30)
)


# ============================================================
# Mostrar los que siguen sin colonia
# ============================================================

sin_colonia = baches_joined[
    baches_joined["colonia"].isna()
]

print(
    "\nBaches que siguen sin colonia:",
    len(sin_colonia),
)

print(
    sin_colonia[
        [
            "id_row",
            "latitude",
            "longitude",
            "colonia_original",
            "settlement_name",
            "spatial_match_method",
            "distance_to_colonia_m",
        ]
    ].head(30)
)


# ============================================================
# Eliminar columnas espaciales auxiliares
# ============================================================

baches_final = baches_joined.drop(
    columns=[
        "geometry",
        "index_right",
    ],
    errors="ignore",
)

baches_final = pd.DataFrame(baches_final)


# ============================================================
# Ordenar columnas relacionadas con colonia
# ============================================================

colonia_columns = [
    "colonia_original",
    "colonia_original_normalized",
    "settlement_name",
    "settlement_name_normalized",
    "settlement_type",
    "colonia_id",
    "spatial_match_method",
    "distance_to_colonia_m",
    "fuera_asentamiento",
    "contexto_ubicacion",
    "colonia_match",
    "colonia",
    "colonia_source",
]

other_columns = [
    column
    for column in baches_final.columns
    if column not in colonia_columns
]

baches_final = baches_final[
    other_columns + colonia_columns
]


# ============================================================
# Resultado final
# ============================================================

print("\n--- Dataset final ---")
print("Shape:", baches_final.shape)
print("\nColumnas:", baches_final.columns.tolist())
print("\nValores NA:")
print(baches_final.isna().sum())


# Dataset reducido para el pipeline final.
# Se conserva TODA la tabla, no solo .head().
baches_clean = baches_final.loc[(baches_final['contexto_ubicacion'] != "dentro_asentamiento")
                                & (baches_final['contexto_ubicacion'] != "cerca_asentamiento")
                                & (baches_final['colonia'].isna()),
    [
        "contexto_ubicacion",
        "fuera_asentamiento",
        "distance_to_colonia_m",
        "latitude",
        "longitude",
        "date",
        "neighborhoods",
        "description",
        "year",
        "date_mx",
        "colonia",
        "colonia_source",
    ]
].copy()

print(len(baches_clean))

print("\nPreview baches_clean:")
print(baches_clean.head())


# ============================================================
# Guardar
# ============================================================
#
# Cuando valides los resultados puedes descomentar:
#
OUTPUT_PATH = (
    baches_processed_directory
    / "baches_hermosillo_colonia_filled.csv"
)

baches_final.to_csv(
    OUTPUT_PATH,
    index=False,
)

print(f"\nArchivo guardado en: {OUTPUT_PATH}")
