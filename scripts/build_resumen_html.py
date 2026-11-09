# /// script
# requires-python = ">=3.12,<3.14"
# dependencies = [
#     "pandas>=2.2",
#     "numpy>=2.0",
#     "geopandas>=1.1",
#     "pyogrio>=0.11",
#     "plotly>=5.24",
#     "matplotlib>=3.9",
#     "scikit-learn>=1.5",
# ]
# ///
"""Genera docs/resumen_edas.html: resumen estilo blog del EDAs.pdf (los 4 EDA
geoespaciales de notebooks/AAMM: sectores, avisos AguaH, llamadas 911 y baches
contra la red hidrografica) con las mismas graficas del PDF en version
interactiva (Plotly).

    uv run --script scripts/build_resumen_html.py

Los calculos reproducen los de las libretas 05-08 de AAMM: exposicion por
colonia (km de cauce hl dentro del poligono), avisos por sector (menciones de
colonia + cruces geocodificados), llamadas 911 unidas a colonia por nombre
normalizado + equivalencias manuales, distancias del centroide a los 3 tramos
hl mas cercanos y la clasificacion K-Means (k=4) de cercania por colonia.
"""

import json
import re
import unicodedata
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data" / "processed"
EXP = ROOT / "notebooks" / "AAMM" / "notebook_experimentation_data"
OUT = ROOT / "docs" / "resumen_edas.html"

METRICO = 6372  # Conica Conforme de Lambert ITRF2008, metros
ORDEN_SECTORES = ["Norte", "Centro", "Sur"]
COLORES_SECTOR = {"Norte": "#4daf4a", "Centro": "#377eb8", "Sur": "#999999"}
ETIQUETAS_CER = ["Muy cercano", "Cercano", "Lejano", "Muy lejano"]
COLORES_CER = {
    "Muy cercano": "#1a9850",
    "Cercano": "#a6d96a",
    "Lejano": "#fdae61",
    "Muy lejano": "#d73027",
}
MESES = ["ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic"]
MESES_LLUVIA = [7, 8, 9]  # temporada de monzon en Hermosillo (misma constante que nb07)
GRUPOS_AGUA = ["inundacion_directa", "fenomeno_hidrometeorologico"]
COLORES_EVENTO = {
    "corte_programado": "#66c2a5",
    "emergencia": "#fc8d62",
    "otro": "#8da0cb",
    "pipas": "#e78ac3",
    "restablecimiento": "#a6d854",
}


def normalize_name(name):
    """Sin acentos, signos ni minusculas (igual que project_name.text)."""
    decomposed = unicodedata.normalize("NFKD", str(name or ""))
    without_accents = "".join(c for c in decomposed if not unicodedata.combining(c))
    only_words = re.sub(r"[^A-Z0-9 ]", " ", without_accents.upper())
    return re.sub(r"\s+", " ", only_words).strip()


def line_trace(geom_series, name, color, width=1.2):
    """Un solo trace con todos los tramos separados por None (para capas hl)."""
    xs, ys = [], []
    for geom in geom_series.explode(index_parts=False).dropna():
        if geom.is_empty:
            continue
        x, y = geom.coords.xy
        xs.extend(list(x) + [None])
        ys.extend(list(y) + [None])
    return go.Scatter(
        x=xs, y=ys, mode="lines", name=name,
        line=dict(color=color, width=width),
        hoverinfo="skip", showlegend=True,
    )


def fig_html(fig, first=False):
    return fig.to_html(
        full_html=False,
        include_plotlyjs="inline" if first else False,
        config={"displayModeBar": True, "displaylogo": False, "locale": "es"},
    )


# --------------------------------------------------------------------------
# Datos
# --------------------------------------------------------------------------
print("leyendo datos...")
sectores = pd.read_csv(EXP / "colonias_hermosillo.csv", dtype={"colonia_id": str})
sectores["colonia_id"] = sectores["colonia_id"].astype("Int64")
ciudad = sectores[
    sectores["locality_code"].astype(str).str.zfill(4) == "0001"
].copy()

colonias = gpd.read_file(DATA / "aguah" / "colonias_hermosillo.gpkg")
colonias_ciudad = colonias[colonias["locality_code"] == "0001"].to_crs(METRICO)
colonias_ciudad["colonia_id"] = colonias_ciudad["colonia_id"].astype("Int64")
colonias_ciudad = colonias_ciudad.merge(
    sectores[["colonia_id", "sector"]], on="colonia_id", how="left"
)

hl_full = gpd.read_file(DATA / "inegi/hidrografia_hermosillo" / "subc_hermosillo.gpkg", layer="hl")
hl_m = hl_full.to_crs(METRICO)

publicaciones = pd.read_csv(DATA / "aguah" / "publicaciones_aguah.csv", dtype={"post_id": str})
ubicaciones = pd.read_csv(DATA / "aguah" / "ubicaciones_aviso.csv", dtype={"post_id": str, "colonia_id": str})
llamadas = pd.read_csv(DATA / "llamadas_911" / "llamadas_911_hermosillo.csv")
baches = pd.read_csv(DATA / "bachometro" / "baches_hermosillo_colonia_filled.csv")

# areas y conteos de colonia por sector
sector_area = (
    colonias_ciudad.dropna(subset=["sector"])
    .groupby("sector")
    .agg(area_km2=("geometry", lambda g: g.area.sum() / 1e6), colonias=("sector", "size"))
)

# km de cauce hl dentro de cada colonia (patron expo de nb06/nb08)
pares = gpd.sjoin(
    hl_m[["geometry"]], colonias_ciudad[["colonia_id", "geometry"]],
    how="inner", predicate="intersects",
)
geom_colonia = pares["colonia_id"].map(colonias_ciudad.set_index("colonia_id")["geometry"])
km_cauce = (
    pares.geometry.intersection(geom_colonia).length
    .groupby(pares["colonia_id"]).sum() / 1000
)
expo = colonias_ciudad.set_index("colonia_id")
expo["area_km2"] = expo.geometry.area / 1e6
expo["km_cauce"] = km_cauce.reindex(expo.index, fill_value=0)

# menciones y cruces geocodificados (los usa el mapa y las figs de avisos)
menciones = ubicaciones.merge(
    publicaciones[["post_id", "event_type", "year", "month"]], on="post_id", how="left"
)
geocod = menciones[menciones["match_method"] == "cruce_geocodificado"]

# --------------------------------------------------------------------------
# Fig 1: mapa de colonias por sector + red hl (recorte ciudad + 1 km)
# --------------------------------------------------------------------------
print("fig 1: mapa de sectores...")
zona1k = colonias_ciudad.union_all().buffer(1000)
hl_cerca = hl_m[hl_m.intersects(colonias_ciudad.union_all().buffer(5000))]
hl_mapa = hl_m[hl_m.intersects(zona1k)]

fig_mapa = go.Figure()
# poligonos de colonias como paths SVG (un trace por sector, con hover)
for s in ORDEN_SECTORES:
    xs, ys, texts = [], [], []
    for _, row in colonias_ciudad[colonias_ciudad["sector"] == s].iterrows():
        geoms = row.geometry.geoms if row.geometry.geom_type == "MultiPolygon" else [row.geometry]
        nombre = row.get("settlement_name", "")
        for poly in geoms:
            x, y = poly.exterior.coords.xy
            xs.extend(list(x) + [None])
            ys.extend(list(y) + [None])
            texts.append(nombre)
    fig_mapa.add_trace(go.Scatter(
        x=xs, y=ys, fill="toself", mode="lines", name=s,
        line=dict(color="white", width=0.4),
        fillcolor=COLORES_SECTOR[s], opacity=0.65,
        hoveron="fills",
        text=[s] * len(xs),
        hovertemplate="%{text}<extra></extra>",
    ))
fig_mapa.add_trace(line_trace(hl_mapa.geometry, "cauces (hl)", "#2166ac", 1.0))
fig_mapa.update_layout(
    title="Colonias de Hermosillo por macro-sector y red hidrográfica",
    yaxis=dict(scaleanchor="x", scaleratio=1),
    xaxis=dict(visible=False), yaxis_visible=False,
    legend=dict(orientation="h", yanchor="bottom", y=-0.08),
    margin=dict(l=10, r=10, t=45, b=10), height=640,
)

# --------------------------------------------------------------------------
# Fig 2: km de cauce/km2 vs. avisos/km2 por sector (nb06)
# --------------------------------------------------------------------------
print("fig 2: exposicion vs avisos...")
menciones_colonia = menciones[menciones["location_type"] == "colonia"].drop_duplicates(
    subset=["post_id", "colonia_id"]
)
menciones_sector = menciones_colonia.merge(
    sectores[["colonia_id", "sector"]].assign(colonia_id=lambda d: d["colonia_id"].astype(str)),
    on="colonia_id", how="left",
)

cruces = gpd.GeoDataFrame(
    geocod.reset_index(drop=True),
    geometry=gpd.points_from_xy(geocod["lon"], geocod["lat"]),
    crs="EPSG:4326",
).to_crs(METRICO)
cruces = gpd.sjoin(
    cruces, colonias_ciudad[["sector", "geometry"]], how="left", predicate="within"
).drop(columns="index_right")
cruces = cruces[~cruces.index.duplicated(keep="first")]

por_sector = (
    expo.dropna(subset=["sector"])
    .groupby("sector")
    .agg(km_cauce=("km_cauce", "sum"))
    .join(sector_area[["area_km2"]])
)
por_sector["menciones"] = menciones_sector.groupby("sector").size()
por_sector["cruces"] = cruces.groupby("sector").size()
por_sector["avisos"] = por_sector["menciones"] + por_sector["cruces"]
por_sector["km_cauce_por_km2"] = por_sector["km_cauce"] / por_sector["area_km2"]
por_sector["avisos_por_km2"] = por_sector["avisos"] / por_sector["area_km2"]

fig_exp = make_subplots(
    cols=2, rows=1,
    subplot_titles=["km de cauce (hl) por km²", "avisos (menciones + cruces) por km²"],
)
fig_exp.add_trace(
    go.Bar(
        x=ORDEN_SECTORES,
        y=por_sector["km_cauce_por_km2"].reindex(ORDEN_SECTORES),
        marker_color="#7fb3d5", name="km cauce/km²",
        hovertemplate="%{x}: %{y:.2f} km/km²<extra></extra>",
    ),
    row=1, col=1,
)
fig_exp.add_trace(
    go.Bar(
        x=ORDEN_SECTORES,
        y=por_sector["avisos_por_km2"].reindex(ORDEN_SECTORES),
        marker_color="#e59866", name="avisos/km²",
        hovertemplate="%{x}: %{y:.1f} avisos/km²<extra></extra>",
    ),
    row=1, col=2,
)
fig_exp.update_layout(
    title="Exposición hidrográfica vs. actividad de avisos por sector",
    showlegend=False, margin=dict(t=60), height=380,
)

# --------------------------------------------------------------------------
# Fig 3: avisos por mes por sector (nb06, anos completos 2021-2025)
# --------------------------------------------------------------------------
print("fig 3: avisos por mes...")
avisos_sector = pd.concat(
    [
        menciones_sector[["post_id", "event_type", "sector"]],
        pd.DataFrame(cruces[["post_id", "event_type", "sector"]]),
    ]
).merge(publicaciones[["post_id", "year", "month"]], on="post_id", how="left")
# la distribucion mensual usa TODAS las menciones con sector (2020-2026), como el PDF;
# las lineas por ano usan solo anos completos (2021-2025)
avisos_all = avisos_sector[avisos_sector["sector"].isin(ORDEN_SECTORES)]
avisos_ns = avisos_all[~avisos_all["year"].isin([2020, 2026])]

pct_js = 100 * avisos_all.groupby("sector")["month"].apply(
    lambda s: s.between(7, 9).mean()
)
pct_js_global = 100 * avisos_all["month"].between(7, 9).mean()

por_mes = (
    avisos_all.groupby(["month", "sector"]).size().unstack("sector")
    .reindex(range(1, 13))[ORDEN_SECTORES]
)
fig_mes = go.Figure()
for s in ORDEN_SECTORES:
    fig_mes.add_trace(go.Bar(
        x=MESES, y=por_mes[s], name=s, marker_color=COLORES_SECTOR[s],
        hovertemplate="%{x}: %{y} menciones<extra>%{fullData.name}</extra>",
    ))
fig_mes.add_vrect(
    x0=5.5, x1=8.5, fillcolor="deepskyblue", opacity=0.15, line_width=0,
    annotation_text="temporada de lluvias (jul-sep)", annotation_position="top left",
)
fig_mes.update_layout(
    title="Avisos por mes por sector — menciones de colonia + cruces (2020–2026)",
    barmode="group", yaxis_title="menciones",
    legend_title="sector", margin=dict(t=60), height=400,
)

# --------------------------------------------------------------------------
# Fig 4: menciones por mes, una linea por ano, por sector (nb06)
# --------------------------------------------------------------------------
print("fig 4: lineas por ano...")
sector_anio_mes = (
    avisos_ns.groupby(["sector", "year", "month"]).size().unstack("month")
    .reindex(columns=range(1, 13)).fillna(0).astype(int)
)
anios = sorted(avisos_ns["year"].unique())
paleta_anio = dict(zip(anios, ["#1f77b4", "#ff7f0e", "#2ca02c", "#d62728", "#9467bd"]))

fig_anio = make_subplots(
    rows=3, cols=1, shared_xaxes=True, vertical_spacing=0.06,
    subplot_titles=[f"{s}" for s in ORDEN_SECTORES],
)
for i, s in enumerate(ORDEN_SECTORES, start=1):
    d = sector_anio_mes.loc[s]
    for a, fila in d.iterrows():
        fig_anio.add_trace(go.Scatter(
            x=MESES, y=fila.values, mode="lines+markers", name=str(a),
            line=dict(color=paleta_anio[a]), marker=dict(size=5),
            legendgroup=str(a), showlegend=(i == 1),
            hovertemplate=f"{s} {a} " + "%{x}: %{y} menciones<extra></extra>",
        ), row=i, col=1)
    fig_anio.add_vrect(
        x0=5.5, x1=8.5, fillcolor="deepskyblue", opacity=0.15, line_width=0,
        row=i, col=1,
    )
fig_anio.update_xaxes(tickvals=list(range(12)), ticktext=MESES, row=3, col=1)
fig_anio.update_layout(
    title="Menciones por mes, una línea por año — años completos 2021–2025 (sombra: jul–sep)",
    legend_title="año", margin=dict(t=60), height=620,
    yaxis_title="menciones", yaxis2_title="menciones", yaxis3_title="menciones",
)

# Norte en 2025 por tipo de evento: el pico de abril (figura del PDF)
TIPOS_EVENTO = ["corte_programado", "emergencia", "otro", "pipas", "restablecimiento"]
norte_2025 = (
    avisos_ns[(avisos_ns["year"] == 2025) & (avisos_ns["sector"] == "Norte")]
    .groupby(["month", "event_type"]).size().unstack("event_type")
    .reindex(range(1, 13)).reindex(columns=TIPOS_EVENTO, fill_value=0)
)
fig_n2025 = go.Figure()
for t in TIPOS_EVENTO:
    fig_n2025.add_trace(go.Bar(
        x=MESES, y=norte_2025[t], name=t, marker_color=COLORES_EVENTO[t],
        hovertemplate="%{x} " + t + ": %{y} menciones<extra></extra>",
    ))
fig_n2025.add_vrect(
    x0=5.5, x1=8.5, fillcolor="deepskyblue", opacity=0.15, line_width=0,
)
fig_n2025.update_layout(
    title="Norte: avisos por mes y tipo de evento (2025)",
    barmode="stack", yaxis_title="menciones", legend_title="event_type",
    margin=dict(t=60), height=400,
)

# --------------------------------------------------------------------------
# Fig 5: union de llamadas 911 a colonias (nb07) + km cauce vs llamadas/km2
# --------------------------------------------------------------------------
print("fig 5: llamadas 911...")
llamadas["fecha"] = pd.to_datetime(llamadas["fecha"])
llamadas["anio"] = llamadas["fecha"].dt.year
llamadas["mes"] = llamadas["fecha"].dt.month

ciudad["nombre_norm"] = ciudad["settlement_name"].map(normalize_name)
llamadas["nombre_norm"] = llamadas["colonia"].map(normalize_name)
catalogo = (
    ciudad[["colonia_id", "nombre_norm", "sector", "area_km2"]]
    .drop_duplicates("nombre_norm")
)
catalogo["colonia_id"] = catalogo["colonia_id"].astype(str)
llamadas = llamadas.merge(catalogo, on="nombre_norm", how="left")

# equivalencias revisadas a mano (nb07)
eq = pd.read_csv(EXP / "equivalencias_colonias_911.csv")
ok = eq[["colonia_911", "OK"]].dropna()
ok = ok[ok["OK"].astype(str).str.strip().str.upper() != "NA"].copy()
ok["nombre_eq"] = ok["OK"].map(normalize_name)
resueltas = ok.merge(catalogo, left_on="nombre_eq", right_on="nombre_norm", how="left")
lookup = resueltas.dropna(subset=["colonia_id"]).set_index("colonia_911")
for col in ["colonia_id", "sector", "area_km2"]:
    llamadas[col] = llamadas[col].fillna(llamadas["colonia"].map(lookup[col]))
con_ll = llamadas.dropna(subset=["colonia_id"])

sector_area_ll = (
    expo.dropna(subset=["sector"])
    .groupby("sector")
    .agg(area_km2=("area_km2", "sum"), km_cauce=("km_cauce", "sum"))
)
sector_area_ll["km_cauce_por_km2"] = sector_area_ll["km_cauce"] / sector_area_ll["area_km2"]
sector_area_ll["llamadas"] = con_ll["sector"].value_counts()
sector_area_ll["llamadas_por_km2"] = sector_area_ll["llamadas"] / sector_area_ll["area_km2"]

# --------------------------------------------------------------------------
# Fig 6: % de llamadas en jul-sep por grupo de incidente (nb07)
# --------------------------------------------------------------------------
print("fig 6: estacionalidad 911...")
llamadas["lluvia"] = llamadas["mes"].isin(MESES_LLUVIA)
temp = (
    llamadas.groupby(["grupo_incidente", "lluvia"]).size().unstack(fill_value=0)
    .rename(columns={False: "no_lluvia", True: "lluvia"})
)
temp["total"] = temp.sum(axis=1)
temp["pct_lluvia"] = temp["lluvia"] / temp["total"] * 100
temp = temp.sort_values("pct_lluvia", ascending=False)

fig_lluvia = go.Figure()
fig_lluvia.add_trace(go.Bar(
    x=temp.index, y=temp["pct_lluvia"],
    marker_color=["#fc8d62" if g in GRUPOS_AGUA else "#7fb3d5" for g in temp.index],
    text=temp["pct_lluvia"].round(1).astype(str) + "%",
    textposition="outside",
    hovertemplate="%{x}: %{y:.1f}% en jul-sep<extra></extra>",
))
fig_lluvia.add_hline(
    y=25, line_dash="dash", line_color="gray",
    annotation_text="25% esperado si fueran uniformes", annotation_position="top left",
)
fig_lluvia.update_layout(
    title="Porcentaje de llamadas en jul–sep por grupo de incidente",
    yaxis_title="% de llamadas del grupo", xaxis_title="",
    yaxis_range=[0, max(45, temp["pct_lluvia"].max() + 8)],
    margin=dict(t=60), height=400,
)

grupos = llamadas["grupo_incidente"].unique().tolist()
set2 = ["#66c2a5", "#fc8d62", "#8da0cb", "#e78ac3", "#a6d854"]

# --------------------------------------------------------------------------
# Fig 8: llamadas/km2 por mes por sector - todos los grupos y solo superficie
# --------------------------------------------------------------------------
print("fig 8: llamadas por mes por sector...")
con_agua = con_ll[con_ll["grupo_incidente"].isin(GRUPOS_AGUA)]

fig_den_mes = make_subplots(
    cols=2, rows=1, shared_yaxes=False, horizontal_spacing=0.08,
    subplot_titles=["todos los grupos", "solo grupos de superficie"],
)
for col, datos in [(1, con_ll), (2, con_agua)]:
    mes_sector = (
        datos.groupby(["mes", "sector"]).size()
        .unstack(fill_value=0).reindex(range(1, 13), fill_value=0)
    )
    for s in ORDEN_SECTORES:
        fig_den_mes.add_trace(go.Bar(
            x=list(range(1, 13)), y=(mes_sector[s] / sector_area_ll.loc[s, "area_km2"]),
            name=s, marker_color=COLORES_SECTOR[s], legendgroup=s,
            showlegend=(col == 1),
            hovertemplate="mes %{x} " + s + ": %{y:.2f} llamadas/km²<extra></extra>",
        ), row=1, col=col)
fig_den_mes.update_layout(
    title="Llamadas por km² por mes y sector",
    barmode="group", yaxis_title="llamadas / km²", yaxis2_title="llamadas / km²",
    legend_title="sector", margin=dict(t=60), height=400,
)

# --------------------------------------------------------------------------
# Fig 9: solo grupos de superficie - tasa por sector y por grupo (nb07)
# --------------------------------------------------------------------------
print("fig 9: tasas de grupos de superficie...")
den_sector = (
    con_ll.groupby(["sector", "grupo_incidente"]).size().unstack(fill_value=0)
    .div(sector_area_ll["area_km2"], axis=0)
)
den_agua = den_sector[GRUPOS_AGUA].sum(axis=1).reindex(ORDEN_SECTORES)

fig_sup = make_subplots(
    cols=2, rows=1, horizontal_spacing=0.1,
    subplot_titles=[
        "llamadas por km² (suma de los 2 grupos)",
        "por grupo de superficie y sector",
    ],
)
fig_sup.add_trace(go.Bar(
    x=ORDEN_SECTORES, y=den_agua, marker_color="#e59866", showlegend=False,
    text=den_agua.round(2), textposition="outside",
    hovertemplate="%{x}: %{y:.2f} llamadas/km²<extra></extra>",
), row=1, col=1)
for g in GRUPOS_AGUA:
    fig_sup.add_trace(go.Bar(
        x=ORDEN_SECTORES, y=den_sector[g].reindex(ORDEN_SECTORES).fillna(0),
        name=g, marker_color=set2[grupos.index(g) % len(set2)],
        text=den_sector[g].reindex(ORDEN_SECTORES).fillna(0).round(2),
        textposition="outside",
        hovertemplate="%{x} " + g + ": %{y:.2f} llamadas/km²<extra></extra>",
    ), row=1, col=2)
fig_sup.update_layout(
    title="Solo grupos ligados a inundación (inundación directa + fenómeno hidrometeorológico)",
    barmode="group", yaxis_title="llamadas / km²", yaxis2_title="llamadas / km²",
    legend=dict(orientation="h", yanchor="top", y=-0.15),
    margin=dict(t=70, b=50), height=420,
)

# --------------------------------------------------------------------------
# Fig 8: baches por km2 por sector (nb08)
# --------------------------------------------------------------------------
print("fig 8: baches por sector...")
baches["date"] = pd.to_datetime(baches["date"], errors="coerce")
baches["mes"] = baches["date"].dt.month
baches["anio"] = baches["date"].dt.year
baches["colonia_id"] = baches["colonia_id"].astype("Int64")
baches = baches.merge(sectores[["colonia_id", "sector"]], on="colonia_id", how="left")
con_sector = baches.dropna(subset=["sector"])

den_baches = (
    con_sector["sector"].value_counts() / sector_area["area_km2"]
).reindex(ORDEN_SECTORES)

fig_baches = go.Figure()
fig_baches.add_trace(go.Bar(
    x=ORDEN_SECTORES, y=den_baches,
    marker_color=[COLORES_SECTOR[s] for s in ORDEN_SECTORES],
    text=den_baches.round(1), textposition="outside",
    hovertemplate="%{x}: %{y:.1f} baches/km²<extra></extra>",
))
fig_baches.update_layout(
    title="Reportes de baches por km², por sector (bachómetro 2021–2026)",
    yaxis_title="baches / km²", showlegend=False,
    margin=dict(t=60), height=380,
)

# hexagonos de concentracion de baches sobre mapa base — misma malla axial de
# la libreta 06-eda-baches (UTM 12N, hexagonos de 500 m de ancho, tope 100)
from shapely.geometry import Polygon

HEX_WIDTH_M = 500.0
MAX_REPORTS_COLOR = 100
HEX_RADIUS_M = HEX_WIDTH_M / np.sqrt(3)

baches_hex = baches.dropna(subset=["latitude", "longitude"])
coords_hex = baches_hex[["longitude", "latitude"]].apply(pd.to_numeric, errors="coerce")
valid_hex = (
    coords_hex["longitude"].between(-180, 180)
    & coords_hex["latitude"].between(-90, 90)
)
points_hex = gpd.GeoDataFrame(
    geometry=gpd.points_from_xy(
        coords_hex.loc[valid_hex, "longitude"], coords_hex.loc[valid_hex, "latitude"]
    ),
    crs="EPSG:4326",
).to_crs("EPSG:32612")


def assign_hexagons(x, y, radius):
    """Indices axiales de una malla hexagonal con vertice superior.

    Redondeo cubico: cada punto pertenece a un solo hexagono,
    incluidos puntos sobre bordes. El origen fijo permite comparar anos.
    """
    q = (np.sqrt(3) / 3 * x - y / 3) / radius
    r = (2 / 3 * y) / radius
    s = -q - r
    rounded = np.rint(np.column_stack([q, r, s]))
    difference = np.abs(rounded - np.column_stack([q, r, s]))
    largest = difference.argmax(axis=1)
    for axis in range(3):
        selected = largest == axis
        other = [i for i in range(3) if i != axis]
        rounded[selected, axis] = -rounded[selected][:, other].sum(axis=1)
    return rounded[:, :2].astype("int64")


hex_ids = assign_hexagons(
    points_hex.geometry.x.to_numpy(), points_hex.geometry.y.to_numpy(), HEX_RADIUS_M
)
hex_counts = (
    pd.DataFrame(hex_ids, columns=["hex_q", "hex_r"])
    .groupby(["hex_q", "hex_r"]).size().reset_index(name="reportes")
)

center_x = HEX_RADIUS_M * np.sqrt(3) * (hex_counts["hex_q"] + hex_counts["hex_r"] / 2)
center_y = HEX_RADIUS_M * 1.5 * hex_counts["hex_r"]
angles = np.deg2rad(np.arange(6) * 60 + 30)
vertices = np.stack([
    center_x.to_numpy()[:, None] + HEX_RADIUS_M * np.cos(angles),
    center_y.to_numpy()[:, None] + HEX_RADIUS_M * np.sin(angles),
], axis=-1)

hex_gdf = gpd.GeoDataFrame(
    hex_counts, geometry=[Polygon(v) for v in vertices], crs="EPSG:32612"
).to_crs("EPSG:4326")

hex_features = [
    {
        "type": "Feature",
        "id": str(i),
        "geometry": {
            "type": "Polygon",
            "coordinates": [[[lon, lat] for lon, lat in poly.exterior.coords]],
        },
    }
    for i, poly in enumerate(hex_gdf.geometry)
]

fig_hex = go.Figure()
fig_hex.add_trace(go.Choroplethmap(
    geojson={"type": "FeatureCollection", "features": hex_features},
    locations=[str(i) for i in range(len(hex_features))],
    z=hex_counts["reportes"], zmin=0, zmax=MAX_REPORTS_COLOR,
    colorscale="YlOrRd", marker_opacity=0.6, marker_line_color="white",
    marker_line_width=0.3,
    colorbar=dict(title="Reportes", tickvals=[0, 20, 40, 60, 80, 100],
                  ticktext=["0", "20", "40", "60", "80", "100 o más"]),
    hovertemplate="%{z} reportes<extra></extra>", name="hexágonos",
))
fig_hex.add_trace(go.Scattermap(
    lat=baches_hex["latitude"], lon=baches_hex["longitude"], mode="markers",
    marker=dict(size=3, opacity=0.5, color="orange"), name="reportes",
    hovertemplate="reporte aislado<extra></extra>",
))
fig_hex.update_layout(
    title="Concentración de reportes de baches por hexágono",
    map_style="carto-voyager",  # OSM da 403 a peticiones automaticas; carto no pide token
    map_center=dict(lat=29.07, lon=-110.97), map_zoom=9.4,
    margin=dict(t=60), height=640,
)

# --------------------------------------------------------------------------
# Fig 9: K-Means de cercania por colonia -> mapa de baches (nb08)
# --------------------------------------------------------------------------
print("fig 9: k-means cercania y mapa de baches...")
geoms = hl_cerca.geometry
sindex = hl_cerca.sindex

cent = colonias_ciudad.set_index("colonia_id").geometry.centroid
d3c = np.empty((len(cent), 3))
for i, p in enumerate(cent):
    cand = list(sindex.query(p.buffer(5000), predicate="intersects"))
    if len(cand) < 3:
        cand = list(sindex.query(p.buffer(15000), predicate="intersects"))
    dist = geoms.iloc[cand].distance(p).to_numpy()
    sel = np.array(cand)[np.argsort(dist)[:3]]
    d3c[i] = geoms.iloc[sel].distance(p).to_numpy()
expo[["d1", "d2", "d3"]] = pd.DataFrame(
    d3c, index=cent.index, columns=["d1", "d2", "d3"]
).reindex(expo.index)

from sklearn.cluster import KMeans

X = expo[["d1", "d2", "d3"]].dropna()
kmean = KMeans(n_clusters=4, n_init=10, random_state=42)
clusters = kmean.fit_predict(X)
orden_cluster = X.assign(c=clusters).groupby("c")["d1"].mean().sort_values().index
mapa_cluster = {c: ETIQUETAS_CER[i] for i, c in enumerate(orden_cluster)}
expo["cercania"] = (
    pd.Series(clusters, index=X.index).map(mapa_cluster)
    .astype(pd.CategoricalDtype(ETIQUETAS_CER, ordered=True))
)
con_sector["cercania"] = con_sector["colonia_id"].map(expo["cercania"])

# baches a coordenadas metricas para aspecto correcto
baches_geo = gpd.points_from_xy(con_sector["longitude"], con_sector["latitude"])
baches_m = gpd.GeoSeries(baches_geo, crs="EPSG:4326").to_crs(METRICO)
con_sector = con_sector.assign(x=baches_m.x.values, y=baches_m.y.values)

fig_bmap = go.Figure()
# colonias de fondo por sector (contornos, muy tenue)
for s in ORDEN_SECTORES:
    xs, ys = [], []
    for geom in colonias_ciudad.loc[colonias_ciudad["sector"] == s, "geometry"]:
        polys = geom.geoms if geom.geom_type == "MultiPolygon" else [geom]
        for poly in polys:
            x, y = poly.exterior.coords.xy
            xs.extend(list(x) + [None])
            ys.extend(list(y) + [None])
    fig_bmap.add_trace(go.Scatter(
        x=xs, y=ys, mode="lines", name=s, legendgroup="sectores",
        legendgrouptitle_text="sector",
        line=dict(color=COLORES_SECTOR[s], width=0.5), opacity=0.4,
        hoverinfo="skip",
    ))
fig_bmap.add_trace(line_trace(hl_mapa.geometry, "cauces (hl)", "#2166ac", 1.0))
for et in reversed(ETIQUETAS_CER):
    sub = con_sector[con_sector["cercania"] == et]
    fig_bmap.add_trace(go.Scattergl(
        x=sub["x"], y=sub["y"], mode="markers", name=et,
        legendgroup="cercania", legendgrouptitle_text="cercanía de la colonia",
        marker=dict(color=COLORES_CER[et], size=3, opacity=0.45),
        hovertemplate=et + "<extra>bache</extra>",
    ))
fig_bmap.update_layout(
    title="Reportes de bache coloreados por la cercanía de su colonia (K-Means k=4)",
    yaxis=dict(scaleanchor="x", scaleratio=1),
    xaxis=dict(visible=False), yaxis_visible=False,
    margin=dict(l=10, r=10, t=45, b=10), height=640,
)

# --------------------------------------------------------------------------
# Fig 10: baches/km2 por mes por cercania + grid por ano (nb08)
# --------------------------------------------------------------------------
print("fig 10: baches por mes...")
area_ciudad = sector_area["area_km2"].sum()
mes_cer = (
    con_sector.groupby(["mes", "cercania"], observed=True).size()
    .unstack(fill_value=0)
    .reindex(range(1, 13), fill_value=0)
    .reindex(columns=ETIQUETAS_CER, fill_value=0)
)
tasa_mes = mes_cer / area_ciudad

fig_mes_cer = go.Figure()
for et in ETIQUETAS_CER:
    fig_mes_cer.add_trace(go.Scatter(
        x=MESES, y=tasa_mes[et], mode="lines+markers", name=et,
        line=dict(color=COLORES_CER[et]), marker=dict(size=5),
        hovertemplate="%{x}: %{y:.1f} baches/km²<extra>" + et + "</extra>",
    ))
fig_mes_cer.update_layout(
    title="Baches por km² por mes — una línea por clase de cercanía",
    yaxis_title="baches / km²", legend_title="cercanía",
    margin=dict(t=60), height=380,
)

anios_b = sorted(con_sector["anio"].dropna().unique())
mes_anio_cer = (
    con_sector.groupby(["anio", "mes", "cercania"], observed=True).size()
    .unstack(fill_value=0)
)
fig_grid = make_subplots(
    rows=2, cols=3, shared_xaxes=True, shared_yaxes=True,
    subplot_titles=[str(int(a)) for a in anios_b],
    vertical_spacing=0.1, horizontal_spacing=0.05,
)
for k, a in enumerate(anios_b):
    r, c = divmod(k, 3)
    if a not in mes_anio_cer.index:
        continue
    d = (
        mes_anio_cer.loc[a]
        .reindex(range(1, 13), fill_value=0)
        .reindex(columns=ETIQUETAS_CER, fill_value=0)
    ) / area_ciudad
    for et in ETIQUETAS_CER:
        fig_grid.add_trace(go.Scatter(
            x=d.index, y=d[et], mode="lines+markers", name=et,
            line=dict(color=COLORES_CER[et]), marker=dict(size=3),
            legendgroup=et, showlegend=(k == 0),
            hovertemplate=f"{int(a)} " + "%{x}: %{y:.1f}<extra>" + et + "</extra>",
        ), row=r + 1, col=c + 1)
fig_grid.update_xaxes(tickvals=list(range(1, 13)), ticktext=MESES, tickangle=90)
fig_grid.update_layout(
    title="Baches por km² por mes — un panel por año, por cercanía",
    legend_title="cercanía", margin=dict(t=60), height=520,
)

# --------------------------------------------------------------------------
# HTML
# --------------------------------------------------------------------------
print("escribiendo HTML...")
figuras = {
    "mapa": fig_html(fig_mapa, first=True),
    "expo": fig_html(fig_exp),
    "mes": fig_html(fig_mes),
    "anio": fig_html(fig_anio),
    "n2025": fig_html(fig_n2025),
    "lluvia": fig_html(fig_lluvia),
    "den_mes": fig_html(fig_den_mes),
    "sup": fig_html(fig_sup),
    "baches": fig_html(fig_baches),
    "hex": fig_html(fig_hex),
    "bmap": fig_html(fig_bmap),
    "mes_cer": fig_html(fig_mes_cer),
    "grid": fig_html(fig_grid),
}

norte_km = por_sector.loc["Norte", "km_cauce_por_km2"]
centro_km = por_sector.loc["Centro", "km_cauce_por_km2"]
sur_km = por_sector.loc["Sur", "km_cauce_por_km2"]

html = f"""<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Agua y ciudad: resumen del análisis exploratorio — Hermosillo</title>
<style>
  :root {{
    --ink: #26251f;
    --muted: #6f6d64;
    --accent: #2a78d6;
    --rule: #e4e3df;
    --bg: #fbfaf7;
    --card: #ffffff;
  }}
  * {{ box-sizing: border-box; }}
  body {{
    margin: 0; background: var(--bg); color: var(--ink);
    font-family: "Segoe UI", "Helvetica Neue", Arial, sans-serif;
    line-height: 1.65; font-size: 16.5px;
  }}
  .wrap {{ max-width: 780px; margin: 0 auto; padding: 2.5rem 1.25rem 4rem; }}
  header.post {{ border-bottom: 1px solid var(--rule); padding-bottom: 1.5rem; margin-bottom: 1.5rem; }}
  .kicker {{ text-transform: uppercase; letter-spacing: .12em; font-size: .72rem; color: var(--accent); font-weight: 700; }}
  h1 {{ font-size: 2rem; line-height: 1.25; margin: .35rem 0 .6rem; }}
  .meta {{ color: var(--muted); font-size: .85rem; }}
  h2 {{ font-size: 1.35rem; margin: 2.4rem 0 .8rem; border-top: 1px solid var(--rule); padding-top: 1.6rem; }}
  h2 .num {{ color: var(--accent); font-weight: 400; margin-right: .5rem; }}
  p {{ margin: .8rem 0; }}
  figure {{ margin: 1.4rem 0; background: var(--card); border: 1px solid var(--rule); border-radius: 10px; padding: .8rem .8rem .2rem; }}
  figcaption {{ color: var(--muted); font-size: .82rem; padding: .4rem .4rem .7rem; }}
  .nota {{ background: #eef4fb; border-left: 4px solid var(--accent); border-radius: 0 8px 8px 0; padding: .9rem 1.1rem; font-size: .92rem; margin: 1.2rem 0; }}
  .nota strong {{ color: var(--accent); }}
  ul {{ padding-left: 1.3rem; }}
  li {{ margin: .35rem 0; }}
  code {{ background: #f0efe9; border-radius: 4px; padding: .05rem .35rem; font-size: .88em; }}
  footer {{ border-top: 1px solid var(--rule); margin-top: 3rem; padding-top: 1.2rem; color: var(--muted); font-size: .8rem; }}
</style>
</head>
<body>
<div class="wrap">

<header class="post">
  <div class="kicker">Hermosillo</div>
  <h1>Agua y ciudad: ¿Habrá una relación entre los avisos de AguaH, los baches y la red hidrográfica?</h1>
  <div class="meta">Noviembre 2026 · Las gráficas son interactivas.</div>
</header>

<p>Se utilizaron cuatro fuentes de información sobre Hermosillo: 
los <strong>avisos de Agua de Hermosillo</strong> publicados en Facebook 
(2020–2026), las <strong>llamadas al 911</strong> (2018–2025), el
<strong>bachómetro ciudadano</strong> (2021–2026) y la 
<strong>red hidrográfica del INEGI</strong>.</p>

<h2><span class="num">1</span>La ciudad en tres sectores</h2>

<p>La ciudad se dividió en tres 
macro-sectores del Plan de Desarrollo Urbano: <strong>Norte</strong> 
(398 colonias, 55.6 km²), <strong>Centro</strong> (178, 36.9 km²) y 
<strong>Sur</strong> (186, 40 km²). Como los sectores no miden lo mismo, 
se utiliza la tasa de <strong>evento por km²</strong>. Sobre ese mapa se dibuja la red hidrográfica que
naturalmente cruza el área edificada.</p>

<figure>{figuras["mapa"]}
<figcaption>Colonia por colonia, coloreada por macro-sector PDU.</figcaption></figure>

<h2><span class="num">2</span>Avisos de AguaH: ¿más cauces y más avisos en el Norte?</h2>

<p>A la izquierda le damos un número a lo que vimos en el mapa anterior. El Norte concentra
<strong>{norte_km:.1f} km de cauce por km²</strong>, el Sur {sur_km:.1f} y el
Centro solo {centro_km:.1f}. El Centro puede considerarse hidrográficamente otra ciudad.
A la derecha tenemos que el Norte <strong>concentra 173 puntos geográficos mencionados por el AguaH por km²</strong>, el Sur 102 y el Centro 58.
El Norte gana en ambas.</p>

<figure>{figuras["expo"]}
<figcaption>Izquierda: kilómetros de cauce que cruzan las colonias de cada
sector, por km². Derecha: puntos geográficos mencionados por km².</figcaption></figure>

<p>Al agrupar las menciones por mes apareció en la temporada de
lluvias: entre julio y septiembre cae el {pct_js_global:.0f}% de los avisos del
año. Si los puntos geográficos mencionados fueran uniformes en el año, julio–septiembre debería juntar ~25% del total</p>

<figure>{figuras["mes"]}
<figcaption>Menciones de puntos geográficos por mes y sector —nombre de colonia o cruce de
calles, todos los años (2020–2026)—. La banda azul marca
julio–septiembre, la temporada de lluvias.</figcaption></figure>

<p>El patrón de picos en temporada de lluvias se repite. Destaca abril
de 2025 en el Norte con un pico.</p>

<figure>{figuras["anio"]}
<figcaption>La misma serie desglosada por año y por sector (solo años
completos 2021-2025).</figcaption></figure>

<p>El pico de abril de 2025 en el Norte llama la atención: son emergencias y
cortes programados. En plena temporada de sequía, Agua de Hermosillo
anunció la incorporación de más agua a la red para mejorar el abasto de las
colonias del norte, lo que implicó un cierre programado el domingo 6 de abril
en ~90 colonias (pozos de Malvinas y Victoria detenidos). Referencias:
<a href="https://aguadehermosillo.gob.mx/aguah/2025/04/04/sera-incorporada-mas-agua-a-la-red-para-mejorar-el-abasto-a-colonias-del-norte-de-la-ciudad/">Boletín AguaH, 4-abr-2025</a>
·
<a href="https://www.nmas.com.mx/sonora/sociedad/suspenden-servicio-agua-hermosillo-6-abril-2025-90-colonias-sin-suministro/">N+, abr-2025</a>.</p>

<p>Lo contrario a lo esperado, no solo la lluvia repercute, también lo hace la sequía.</p>

<figure>{figuras["n2025"]}
<figcaption>Solo el Norte en 2025, desglosado por tipo de aviso: el pico de
abril son emergencias y cortes programados.</figcaption></figure>

<h2><span class="num">3</span>Llamadas 911: débil relación espacial y naturalmente temporal</h2>

<p>Las llamadas al 911 se agruparon en cinco tipos de incidente según su
relación con el agua: <code>terreno</code>, <code>drenaje y red de agua</code>,
<code>inundacion directa</code>, <code>fenomeno hidrometeorologico</code> y
<code>ahogamiento acuaticos</code>. El análisis consistió en 3,545 llamadas que pudieron 
ser ubicadas en una colonia de la ciudad.</p>

<p>Si las llamadas fueran uniformes
en el año, julio–septiembre debería juntar ~25% del total. Los grupos ligados a
agua en superficie lo superan con claridad, recordando que es una asociación temporal, no prueba
causal.</p>

<figure>{figuras["lluvia"]}
<figcaption>Porcentaje de las llamadas de cada grupo que cae en jul–sep.</figcaption></figure>

<p>Con los 5 grupos, el Centro
concentra la mayor tasa; al quedarnos solo con los dos grupos ligados con mayor relación 
temporal y relación con la lluvia (inundaciones y fenomenos hidrometeorologicos), 
el Norte presenta un 3.18 llamadas por km², el Sur con 3 llamadas por km² y el centro con 2.36 llamadas por km².</p>

<figure>{figuras["den_mes"]}
<figcaption>Llamadas por km² por mes y sector.</figcaption></figure>

<h2><span class="num">4</span>Baches: el Norte reporta más</h2>

<p>Del bachómetro se analizaron 38,209 reportes. El Norte reporta más
baches que el Centro y casi el doble que el Sur.</p>

<figure>{figuras["baches"]}
<figcaption>Reportes de bache por km² por sector (sep 2021 – sep 2026).</figcaption></figure>

<figure>{figuras["hex"]}
<figcaption>Concentración de reportes de baches por hexágono — cada celda
colorea por número de reportes; los puntos sueltos son reportes aislados fuera
de las zonas densas.</figcaption></figure>

<h2><span class="num">5</span>Qué queda pendiente</h2>

<ul>
  <li>Las relaciones encontradas son <strong>asociativas</strong>: sin datos de
  precipitación ni de población por colonia no se puede declarar causalidad ni
  distinguir "drenaje bueno" de "nadie vive ahí".</li>
  <li>El ~30% de las llamadas 911 que no emparejó con el catálogo queda fuera
  del análisis espacial.</li>
</ul>

<footer>
Generado con <code>scripts/build_resumen_html.py</code> · Datos:
data/processed (AguaH, 911, bachómetro, INEGI hidrografía)
</footer>

</div>
</body>
</html>
"""

OUT.write_text(html, encoding="utf-8")
print(f"listo -> {OUT} ({OUT.stat().st_size / 1e6:.1f} MB)")
