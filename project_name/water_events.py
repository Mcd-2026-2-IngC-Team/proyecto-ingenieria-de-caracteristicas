"""Cargas y cálculos de la exploración de redefinición (notebook 08).

Junta en una tabla diaria la lluvia de Open-Meteo con los conteos de las fuentes del
proyecto (llamadas al 911, baches y publicaciones de Agua de Hermosillo), para medir
cuánto de cada serie responde a la lluvia. Lo usan el notebook 08 y el script que dibuja
la figura del reporte, así las cifras de ambos salen del mismo código.
"""

import geopandas as gpd
import numpy as np
import pandas as pd

from project_name.config import PROJECT_ROOT
from project_name.text import normalize_name

PROCESSED = PROJECT_ROOT / "data" / "processed"
RAIN_FILE = PROCESSED / "precipitacion" / "precipitacion_hermosillo.csv"
CALLS_FILE = PROCESSED / "llamadas_911" / "llamadas_911_hermosillo.csv"
BACHES_FILE = PROCESSED / "bachometro" / "baches_hermosillo.csv"
BACHES_LOCATED_FILE = PROCESSED / "bachometro" / "baches_hermosillo_filled.csv"
POSTS_FILE = PROCESSED / "aguah" / "publicaciones_aguah.csv"
COLONIAS_FILE = PROCESSED / "aguah" / "colonias_hermosillo.gpkg"
SUBCUENCAS_FILE = PROCESSED / "inegi" / "hidrografia_hermosillo" / "subc_hermosillo.gpkg"

METRIC_CRS = "EPSG:6372"
CITY_LOCALITY = "0001"

# Periodo de cada fuente con meses completos; fuera de él la serie no está cubierta.
COVERAGE = {
    "lluvia": ("2018-01-01", "2026-09-30"),
    "911": ("2018-01-01", "2025-09-30"),
    "baches": ("2022-01-01", "2026-09-30"),
    "aguah": ("2021-01-01", "2026-07-31"),
}

# Umbral de un día "de lluvia que escurre" en el reanálisis y ventana de respuesta.
RAIN_EVENT_MM = 10.0
RESPONSE_DAYS = 8
DRY_MM = 1.0
RAINY_MONTHS = [6, 7, 8, 9, 10]


def load_rain() -> pd.Series:
    rain = pd.read_csv(RAIN_FILE, parse_dates=["date"])
    return rain.set_index("date")["precipitation_mm"]


def load_colonias() -> gpd.GeoDataFrame:
    colonias = gpd.read_file(COLONIAS_FILE)
    return colonias[colonias["locality_code"] == CITY_LOCALITY].reset_index(drop=True)


def match_colonia(names: pd.Series, colonias: pd.DataFrame) -> pd.Series:
    """colonia_id por nombre normalizado; solo cuando el nombre es único en la ciudad."""
    catalog = colonias.groupby("settlement_name_normalized")["colonia_id"].agg(list)
    unique = catalog[catalog.map(len) == 1].map(lambda ids: ids[0])
    return names.astype(str).map(normalize_name).map(unique)


def load_calls(colonias: pd.DataFrame | None = None) -> pd.DataFrame:
    """Llamadas al 911; con `colonias`, cada llamada queda con su colonia de la ciudad.

    La colonia viene de `add_colonia_llamada_job` (nombre normalizado contra el catálogo
    del INEGI más la tabla de equivalencias revisada a mano). Si el CSV procesado aún no
    la trae, se usa el emparejamiento por nombre único como respaldo. Las colonias fuera
    de la localidad 0001 (la ciudad) quedan sin asignar.
    """
    calls = pd.read_csv(CALLS_FILE, parse_dates=["fecha"], dtype={"colonia_id": str}).rename(
        columns={"fecha": "date"}
    )
    if colonias is not None:
        if "colonia_id" not in calls:
            calls["colonia_id"] = match_colonia(calls["colonia"], colonias)
        city = set(colonias["colonia_id"])
        calls["colonia_id"] = calls["colonia_id"].where(calls["colonia_id"].isin(city))
    return calls


def load_baches() -> pd.DataFrame:
    return pd.read_csv(BACHES_FILE, parse_dates=["date"])


def load_baches_located(colonias: pd.DataFrame) -> pd.DataFrame:
    """Baches con colonia de la ciudad (`add_colonia_bache_id_with_gpkg`).

    La fecha del Bachómetro es la de atención del bache, no la de su aparición: sirve
    para comparar lugares, no para medir la respuesta a la lluvia.
    """
    baches = pd.read_csv(BACHES_LOCATED_FILE, parse_dates=["date"], dtype={"colonia_id": str})
    city = set(colonias["colonia_id"])
    baches["colonia_id"] = baches["colonia_id"].where(baches["colonia_id"].isin(city))
    return baches


def load_posts() -> pd.DataFrame:
    posts = pd.read_csv(POSTS_FILE)
    # published_at ya viene en hora local de Hermosillo; basta con la fecha.
    posts["date"] = pd.to_datetime(posts["published_at"].str[:10])
    return posts


def daily_counts(frame: pd.DataFrame, source: str) -> pd.Series:
    start, end = COVERAGE[source]
    days = pd.date_range(start, end, name="date")
    return frame.groupby("date").size().reindex(days, fill_value=0)


def daily_table(rain: pd.Series, series: dict[str, pd.Series]) -> pd.DataFrame:
    """Una fila por día con la lluvia, su máximo reciente y cada conteo."""
    table = pd.DataFrame({"rain_mm": rain})
    # Máximo de lluvia del día y los RESPONSE_DAYS - 1 anteriores: si cae arriba del
    # umbral, el día está dentro de la ventana de respuesta a un evento de lluvia.
    table["recent_max_mm"] = rain.rolling(RESPONSE_DAYS, min_periods=1).max()
    for name, counts in series.items():
        table[name] = counts
    table["month"] = table.index.month
    table["year_month"] = table.index.to_period("M")
    return table


def lagged_spearman(table: pd.DataFrame, column: str, lags: list[int]) -> pd.Series:
    """Spearman entre la lluvia del día t y el conteo del día t + k."""
    frame = table[["rain_mm", column]].dropna()
    return pd.Series(
        {lag: frame["rain_mm"].corr(frame[column].shift(-lag), method="spearman") for lag in lags},
        name=column,
    )


def event_study(table: pd.DataFrame, column: str) -> dict:
    """Conteo diario medio dentro de la ventana de respuesta contra días secos.

    Se compara solo dentro de los meses lluviosos para que la estacionalidad no se
    confunda con la respuesta a la lluvia.
    """
    frame = table[table["month"].isin(RAINY_MONTHS)][["recent_max_mm", column]].dropna()
    wet = frame["recent_max_mm"] >= RAIN_EVENT_MM
    dry = frame["recent_max_mm"] < DRY_MM
    wet_mean, dry_mean = frame.loc[wet, column].mean(), frame.loc[dry, column].mean()
    return {
        "serie": column,
        "días tras lluvia": int(wet.sum()),
        "media tras lluvia": round(wet_mean, 2),
        "días secos": int(dry.sum()),
        "media en secos": round(dry_mean, 2),
        "razón": round(wet_mean / dry_mean, 2) if dry_mean else np.nan,
    }


def within_month_ratio(table: pd.DataFrame, column: str) -> pd.DataFrame:
    """Razón húmedo/seco calculada dentro de cada mes calendario de cada año."""
    frame = table[["recent_max_mm", column, "year_month"]].dropna()
    frame = frame.assign(
        kind=np.select(
            [frame["recent_max_mm"] >= RAIN_EVENT_MM, frame["recent_max_mm"] < DRY_MM],
            ["húmedo", "seco"],
            default="otro",
        )
    )
    means = (
        frame[frame["kind"] != "otro"]
        .groupby(["year_month", "kind"])[column]
        .mean()
        .unstack()
        .dropna()
    )
    means["razón"] = means["húmedo"] / means["seco"]
    return means


def monthly_share(frame: pd.DataFrame, years: list[int]) -> pd.DataFrame:
    """Participación (%) de cada mes en el total anual, un renglón por año."""
    subset = frame[frame["date"].dt.year.isin(years)]
    counts = pd.crosstab(subset["date"].dt.year, subset["date"].dt.month)
    counts = counts.reindex(columns=range(1, 13), fill_value=0)
    return counts.div(counts.sum(axis=1), axis=0).mul(100).round(1)


INTENSITY_BINS = [-0.1, 0.99, 9.99, 19.99, 39.99, 1000]
INTENSITY_LABELS = ["seco (<1 mm)", "1 a 10 mm", "10 a 20 mm", "20 a 40 mm", "40 mm o más"]
EVENT_MM = 20.0


def rain_related_calls(calls: pd.DataFrame) -> pd.DataFrame:
    """Llamadas que puede provocar una lluvia: todo el filtro del 911 menos ahogamientos."""
    return calls[calls["grupo_incidente"] != "ahogamiento_acuaticos"]


def calls_by_intensity(rain: pd.Series, calls: pd.DataFrame) -> pd.DataFrame:
    """Llamadas del mismo día según cuánto llovió ese día, de junio a octubre."""
    start, end = COVERAGE["911"]
    days = pd.date_range(start, end)
    frame = pd.DataFrame(
        {
            "rain_mm": rain.reindex(days),
            "llamadas": calls.groupby("date").size().reindex(days, fill_value=0),
        }
    )
    frame = frame[frame.index.month.isin(RAINY_MONTHS)]
    frame["intensidad"] = pd.cut(frame["rain_mm"], INTENSITY_BINS, labels=INTENSITY_LABELS)
    return frame.groupby("intensidad", observed=False)["llamadas"].agg(
        dias="size",
        promedio="mean",
        dia_malo=lambda values: values.quantile(0.9),
        maximo="max",
    )


def event_curve(rain: pd.Series, calls: pd.DataFrame, offsets=range(-3, 8)) -> pd.DataFrame:
    """Llamadas medias en los días alrededor de una lluvia de EVENT_MM o más.

    Solo cuenta lluvias aisladas (sin 10 mm o más en los 3 días anteriores), para que
    el día 0 sea de verdad el inicio del evento. Los eventos caen en cualquier mes (en
    invierno también hay lluvias fuertes), así que el día seco de referencia se toma de
    todo el año, no solo de la temporada.
    """
    start, end = COVERAGE["911"]
    days = pd.date_range(start, end)
    daily_rain = rain.reindex(days)
    counts = calls.groupby("date").size().reindex(days, fill_value=0)
    previous = daily_rain.shift(1).rolling(3, min_periods=1).max()
    events = days[(daily_rain >= EVENT_MM) & (previous < RAIN_EVENT_MM)]
    curve = pd.DataFrame(
        {
            "dia": list(offsets),
            "llamadas": [
                counts.reindex(events + pd.Timedelta(days=offset)).mean() for offset in offsets
            ],
        }
    )
    dry_days = counts[daily_rain < DRY_MM]
    return curve.assign(
        eventos=len(events),
        eventos_en_temporada=int(events.month.isin(RAINY_MONTHS).sum()),
        dia_seco=dry_days.mean(),
    )


def response_window(rain: pd.Series) -> pd.Series:
    """Máximo de lluvia del día y los RESPONSE_DAYS - 1 anteriores."""
    return rain.rolling(RESPONSE_DAYS, min_periods=1).max()


def extra_calls_by_type(rain: pd.Series, calls: pd.DataFrame) -> pd.DataFrame:
    """Llamadas por día de cada tipo tras una lluvia de 10 mm o más contra días secos."""
    window = response_window(rain)
    start, end = COVERAGE["911"]
    days = pd.date_range(start, end)
    season = days[days.month.isin(RAINY_MONTHS)]
    wet_days = season[window.reindex(season) >= RAIN_EVENT_MM]
    dry_days = season[window.reindex(season) < DRY_MM]
    tipo = calls["tipo_incidente"]
    table = pd.DataFrame(
        {
            "tras lluvia": tipo[calls["date"].isin(wet_days)].value_counts() / len(wet_days),
            "días secos": tipo[calls["date"].isin(dry_days)].value_counts() / len(dry_days),
        }
    ).fillna(0)
    table["extra por día"] = table["tras lluvia"] - table["días secos"]
    return table.sort_values("extra por día", ascending=False)


def hour_profile(rain: pd.Series, calls: pd.DataFrame) -> pd.DataFrame:
    """Reparto (%) de las llamadas por hora: días con 10 mm o más contra días secos."""
    same_day = calls["date"].map(rain)
    dry = calls["date"].map(response_window(rain)) < DRY_MM
    return (
        pd.DataFrame(
            {
                "día de lluvia": calls.loc[same_day >= RAIN_EVENT_MM, "hora"].value_counts(
                    normalize=True
                ),
                "día seco": calls.loc[dry, "hora"].value_counts(normalize=True),
            }
        )
        .reindex(range(24), fill_value=0)
        .mul(100)
    )


def seasons_with_calls(rain: pd.Series, calls: pd.DataFrame) -> pd.DataFrame:
    """Por colonia: llamadas tras lluvia y en cuántas temporadas (años) las hubo."""
    located = calls[calls["colonia_id"].notna()]
    wet = located[located["date"].map(response_window(rain)) >= RAIN_EVENT_MM]
    return wet.groupby("colonia_id").agg(
        llamadas=("date", "size"), temporadas=("date", lambda dates: dates.dt.year.nunique())
    )


def stream_distance(colonias: gpd.GeoDataFrame, buffer_m: float = 5000) -> pd.Series:
    """Distancia (m) del centroide de cada colonia al tramo de cauce más cercano.

    Mismo criterio que notebooks/AAMM/07: tramos `hl` de las cuatro subcuencas que caen
    a menos de `buffer_m` de la ciudad, en una proyección métrica.
    """
    streams = gpd.read_file(SUBCUENCAS_FILE, layer="hl").to_crs(METRIC_CRS)
    city = colonias.to_crs(METRIC_CRS)
    zone = city.union_all().buffer(buffer_m)
    streams = streams[streams.intersects(zone)]
    centroids = city.set_index("colonia_id").geometry.centroid
    nearest = gpd.sjoin_nearest(
        gpd.GeoDataFrame(geometry=centroids), streams[["geometry"]], distance_col="distance_m"
    )
    # sjoin_nearest repite la colonia si dos tramos empatan en distancia.
    return nearest.groupby(level=0)["distance_m"].min().rename("stream_distance_m")


# ---------------------------------------------------------------------------------
# Contexto hidrográfico (notebook 10): dónde, cruzado con cuándo.
# ---------------------------------------------------------------------------------

CONTEXT_FILE = (
    PROCESSED / "inegi" / "hidrografia_hermosillo" / "colonias_contexto_hidrografico.csv"
)
UBICACIONES_FILE = PROCESSED / "aguah" / "ubicaciones_aviso.csv"
# Grupos del 911 que el reporte hidrográfico llama "de superficie".
SURFACE_GROUPS = ["inundacion_directa", "fenomeno_hidrometeorologico"]


def load_contexts() -> pd.DataFrame:
    return pd.read_csv(CONTEXT_FILE, dtype={"colonia_id": str})


def context_area(colonias: gpd.GeoDataFrame, contexts: pd.DataFrame) -> pd.Series:
    """km² de cada contexto: suma del área de sus colonias (EPSG:6372)."""
    area = colonias.to_crs(METRIC_CRS).set_index("colonia_id").geometry.area / 1e6
    context = contexts.set_index("colonia_id")["context"]
    return area.groupby(context.reindex(area.index)).sum().rename("km2")


def aviso_counts(colonias: gpd.GeoDataFrame, months: list[int] | None = None) -> pd.Series:
    """Avisos de Agua de Hermosillo por colonia: menciones de colonia más cruces.

    Mismo criterio que el reporte hidrográfico: las menciones cuentan por su colonia y
    los cruces geocodificados por el polígono en el que caen.
    """
    mentions = pd.read_csv(UBICACIONES_FILE, dtype={"colonia_id": str})
    posts = pd.read_csv(POSTS_FILE, usecols=["post_id", "month"])
    mentions = mentions.merge(posts, on="post_id", how="left")
    if months is not None:
        mentions = mentions[mentions["month"].isin(months)]
    by_name = mentions[mentions["location_type"] == "colonia"].groupby("colonia_id").size()
    crossings = mentions[mentions["match_method"] == "cruce_geocodificado"]
    points = gpd.GeoDataFrame(
        geometry=gpd.points_from_xy(crossings["lon"], crossings["lat"]), crs="EPSG:4326"
    ).to_crs(METRIC_CRS)
    inside = gpd.sjoin(
        points, colonias.to_crs(METRIC_CRS)[["colonia_id", "geometry"]], predicate="within"
    )
    inside = inside[~inside.index.duplicated(keep="first")]
    by_point = inside.groupby("colonia_id").size()
    return by_name.add(by_point, fill_value=0)


def context_rates(
    colonias: gpd.GeoDataFrame,
    contexts: pd.DataFrame,
    calls: pd.DataFrame,
    baches: pd.DataFrame,
    months: list[int] | None = None,
    call_groups: list[str] = SURFACE_GROUPS,
) -> pd.DataFrame:
    """Reportes por km² de cada contexto: avisos, llamadas de los grupos dados y baches."""
    context = contexts.set_index("colonia_id")["context"]
    area = context_area(colonias, contexts)

    def per_km2(counts_by_colonia: pd.Series) -> pd.Series:
        by_context = counts_by_colonia.groupby(context.reindex(counts_by_colonia.index)).sum()
        return by_context / area

    selected_calls = calls[calls["grupo_incidente"].isin(call_groups)]
    selected_baches = baches
    if months is not None:
        selected_calls = selected_calls[selected_calls["date"].dt.month.isin(months)]
        selected_baches = baches[baches["date"].dt.month.isin(months)]
    return pd.DataFrame(
        {
            "avisos": per_km2(aviso_counts(colonias, months)),
            "llamadas": per_km2(selected_calls.groupby("colonia_id").size()),
            "baches": per_km2(selected_baches.groupby("colonia_id").size()),
        }
    )


def context_daily_series(
    calls: pd.DataFrame, contexts: pd.DataFrame, groups: list[str]
) -> dict[str, pd.Series]:
    """Conteo diario de llamadas ubicadas de los grupos dados, una serie por contexto."""
    context = contexts.set_index("colonia_id")["context_name"]
    located = calls[calls["grupo_incidente"].isin(groups)].copy()
    located["context_name"] = located["colonia_id"].map(context)
    return {
        name: daily_counts(located[located["context_name"] == name], "911")
        for name in sorted(context.dropna().unique())
    }


def within_month_interval(
    table: pd.DataFrame, column: str, n_boot: int = 2000, seed: int = 42
) -> dict:
    """Razón dentro del mes con intervalo bootstrap del 90% remuestreando meses.

    Los días de un mismo mes no son independientes (comparten la tormenta y la
    temporada), así que la unidad que se remuestrea es el mes completo.
    """
    months = within_month_ratio(table, column)
    rng = np.random.default_rng(seed)
    wet, dry = months["húmedo"].to_numpy(), months["seco"].to_numpy()
    draws = rng.integers(0, len(months), size=(n_boot, len(months)))
    wet_sum, dry_sum = wet[draws].sum(axis=1), dry[draws].sum(axis=1)
    ratios = np.divide(wet_sum, dry_sum, out=np.full(n_boot, np.nan), where=dry_sum > 0)
    low, high = np.nanpercentile(ratios, [5, 95])
    return {
        "serie": column,
        "meses": len(months),
        "razón en el mes": round(wet.sum() / dry.sum(), 2) if dry.sum() else np.nan,
        "intervalo 90% bajo": round(low, 2),
        "intervalo 90% alto": round(high, 2),
    }
