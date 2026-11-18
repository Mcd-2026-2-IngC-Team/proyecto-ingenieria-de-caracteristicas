"""Contexto hidrográfico de cada colonia de la ciudad.

Port del método de `notebooks/AAMM/09-AAMM-ml-exploration.ipynb` (celdas 8 a 24), sin
cambios de criterio, para que el contexto sea un dato procesado y reproducible:

1. Los 3 tramos de cauce (`hl`) más cercanos al centroide de cada colonia, entre los
   tramos a menos de 5 km de la ciudad, en metros (EPSG:6372).
2. Nivel de cercanía: KMeans k=4 sobre las 3 distancias, reetiquetado de Muy cercano a
   Muy lejano según la media de la distancia al primer tramo.
3. Atributos de los tramos habilitados (`ENABLED == 1`; los deshabilitados traen -1 o 0
   como código de "no disponible"): mediana y máximo del orden de Strahler (`ORDER_1`) y
   mediana y mínimo del nivel de corriente (`LEVEL_1`), más la cercanía como ordinal.
4. Estandarizar y KMeans k=4 (`n_init=10`, `random_state=42`).
5. Reetiquetar los grupos por su perfil, con los nombres del reporte hidrográfico.
"""

import geopandas as gpd
import numpy as np
import pandas as pd
from sklearn.cluster import KMeans
from sklearn.preprocessing import StandardScaler

METRIC_CRS = "EPSG:6372"
CITY_BUFFER_M = 5000
SEARCH_RADII_M = (5000, 15000)
RANDOM_STATE = 42
N_CONTEXTS = 4

PROXIMITY_LEVELS = ["Muy cercano", "Cercano", "Lejano", "Muy lejano"]
FEATURES = ["order_median", "order_max", "level_median", "level_min", "proximity_ord"]

CONTEXT_NAMES = {
    0: "Lejos de la red",
    1: "Junto a colectores",
    2: "Arroyos menores muy cerca",
    3: "Los más cercanos",
}


def nearest_segments(
    colonias: gpd.GeoDataFrame, streams: gpd.GeoDataFrame, n: int = 3
) -> pd.DataFrame:
    """Id y distancia (m) de los `n` tramos más cercanos al centroide de cada colonia."""
    city = colonias.to_crs(METRIC_CRS)
    streams = streams.to_crs(METRIC_CRS)
    streams = streams[streams.intersects(city.union_all().buffer(CITY_BUFFER_M))]
    streams = streams.reset_index(drop=True)
    index = streams.sindex
    centroids = city.set_index("colonia_id").geometry.centroid

    ids = np.empty((len(centroids), n), dtype=object)
    distances = np.full((len(centroids), n), np.nan)
    for row, point in enumerate(centroids):
        candidates = []
        # Un radio amplio solo cuando el primero no alcanza a juntar n tramos.
        for radius in SEARCH_RADII_M:
            candidates = list(index.query(point.buffer(radius), predicate="intersects"))
            if len(candidates) >= n:
                break
        found = streams.geometry.iloc[candidates].distance(point).to_numpy()
        chosen = np.array(candidates)[np.argsort(found)[:n]]
        ids[row, : len(chosen)] = streams["ID"].iloc[chosen].to_numpy()
        distances[row, : len(chosen)] = streams.geometry.iloc[chosen].distance(point).to_numpy()

    columns = {}
    for k in range(n):
        columns[f"id_seg_{k + 1}"] = ids[:, k]
        columns[f"dist_seg_{k + 1}"] = distances[:, k]
    return pd.DataFrame(columns, index=centroids.index)


def proximity_level(segments: pd.DataFrame) -> pd.Series:
    """Muy cercano a Muy lejano: KMeans k=4 sobre las tres distancias."""
    distances = segments[["dist_seg_1", "dist_seg_2", "dist_seg_3"]].to_numpy()
    labels = KMeans(n_clusters=4, n_init=10, random_state=RANDOM_STATE).fit_predict(distances)
    order = (
        pd.DataFrame({"label": labels, "d1": distances[:, 0]})
        .groupby("label")["d1"]
        .mean()
        .sort_values()
        .index
    )
    names = {label: PROXIMITY_LEVELS[rank] for rank, label in enumerate(order)}
    return pd.Series(
        pd.Categorical([names[label] for label in labels], PROXIMITY_LEVELS, ordered=True),
        index=segments.index,
        name="proximity_level",
    )


def segment_features(segments: pd.DataFrame, streams: pd.DataFrame) -> pd.DataFrame:
    """Orden y nivel de los tramos cercanos habilitados, resumidos por colonia."""
    long = pd.concat(
        [
            segments[[f"id_seg_{k}"]].rename(columns={f"id_seg_{k}": "ID"}).reset_index()
            for k in (1, 2, 3)
        ],
        ignore_index=True,
    )
    attributes = streams[["ID", "ORDER_1", "LEVEL_1", "ENABLED"]].drop_duplicates("ID")
    long = long.merge(attributes, on="ID", how="left")
    long = long[long["ENABLED"] == 1]
    return long.groupby("colonia_id").agg(
        order_median=("ORDER_1", "median"),
        order_max=("ORDER_1", "max"),
        level_median=("LEVEL_1", "median"),
        level_min=("LEVEL_1", "min"),
    )


def relabel_by_profile(frame: pd.DataFrame, labels: pd.Series) -> pd.Series:
    """Asigna los nombres del reporte hidrográfico según el perfil de cada grupo.

    El número que da KMeans es arbitrario; este paso lo vuelve estable: el grupo más
    lejano es 0, el de mayor orden de Strahler entre los restantes es 1, el de mayor
    nivel de corriente (arroyos de cabecera) es 2 y el que queda es 3.
    """
    profile = frame.assign(label=labels).groupby("label")[FEATURES].mean()
    mapping = {}
    remaining = profile.copy()
    for context, column in [(0, "proximity_ord"), (1, "order_median"), (2, "level_median")]:
        label = remaining[column].idxmax()
        mapping[label] = context
        remaining = remaining.drop(index=label)
    mapping[remaining.index[0]] = 3
    return labels.map(mapping)


def hydro_context(
    colonias: gpd.GeoDataFrame, streams: gpd.GeoDataFrame, k: int = N_CONTEXTS
) -> pd.DataFrame:
    """Una fila por colonia con tramos cercanos, cercanía, atributos y contexto."""
    segments = nearest_segments(colonias, streams)
    segments["proximity_level"] = proximity_level(segments)
    frame = segments.join(segment_features(segments, streams))
    frame["proximity_ord"] = frame["proximity_level"].cat.codes.astype(float)

    complete = frame[FEATURES].notna().all(axis=1)
    scaled = StandardScaler().fit_transform(frame.loc[complete, FEATURES])
    labels = KMeans(n_clusters=k, n_init=10, random_state=RANDOM_STATE).fit_predict(scaled)
    labels = pd.Series(labels, index=frame.index[complete])

    frame["context"] = pd.Series(pd.NA, index=frame.index, dtype="Int64")
    if k == N_CONTEXTS:
        frame.loc[complete, "context"] = relabel_by_profile(frame.loc[complete], labels)
        frame["context_name"] = frame["context"].map(CONTEXT_NAMES)
    else:
        frame.loc[complete, "context"] = labels
    return frame.reset_index()


def context_area_km2(colonias: gpd.GeoDataFrame, context: pd.Series) -> pd.Series:
    """km² de cada contexto: suma de las áreas de sus colonias (EPSG:6372)."""
    city = colonias.to_crs(METRIC_CRS).set_index("colonia_id")
    area = city.geometry.area / 1e6
    return area.groupby(context.reindex(area.index)).sum()
