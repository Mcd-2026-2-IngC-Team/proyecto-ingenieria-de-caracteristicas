from pathlib import Path
import re

import geopandas as gpd
from loguru import logger
import pandas as pd

from project_name.config import load_dataset_config, load_logging, load_params
from project_name.geocoding import StreetIndex, build_colonias, read_city_streets
from project_name.logging import log_execution
from project_name.text import normalize_name

HERMOSILLO_CITY = ("030", "0001")
GEOGRAPHIC = 4326

# Nombres muy cortos ("APOLO", "GALA", "PIMA") aparecen dentro de otras palabras y meten
# más ruido del que aportan.
MIN_NAME_LENGTH = 6
COLONIA_MARKER = re.compile(
    r"(COLONIAS?|COL|FRACCIONAMIENTOS?|FRACC|RESIDENCIAL|SECTOR|ASENTAMIENTO)\s*$"
)
STREET_MARKER = re.compile(
    r"(CALLE|BULEVAR|BLVD|AVENIDA|AVE|CALZADA|CARRETERA|PERIFERICO|PROLONGACION"
    r"|RETORNO|CALLEJON)\s*$"
)
# Se llama igual que una colonia pero en los avisos casi siempre es la institución.
INSTITUTIONAL = {"H AYUNTAMIENTO"}
MARKER_LOOKBEHIND = 14

STREET_TYPE = (
    r"(?:calle|bulevar|blvr\.?|blvd\.?|avenida|av\.?|camino|carretera|periférico"
    r"|prolongación|retorno|callejón)"
)
# Un nombre de calle son pocas palabras y nunca cruza un salto de línea; acotarlo evita
# tragarse el resto de la oración ("y bulevar Colosio registrada la mañana de...").
NAME = r"[\wáéíóúñÁÉÍÓÚÑ]+(?:[ \t]+[\wáéíóúñÁÉÍÓÚÑ]+){0,3}"
JOIN = (
    rf"(?:[ \t]+entre[ \t]+{NAME}[ \t]+y[ \t]+{NAME}"
    rf"|[ \t]+entre[ \t]+{NAME}"
    rf"|[ \t]+y[ \t]+(?:{STREET_TYPE}[ \t]+)?{NAME})"
)
CROSSING_PATTERN = re.compile(rf"{STREET_TYPE}[ \t]+({NAME}{JOIN})", re.IGNORECASE)

COLUMNS = [
    "post_id",
    "location_type",
    "raw_text",
    "colonia_id",
    "lat",
    "lon",
    "source_field",
    "match_method",
]
# Declaradas para que un lote sin menciones, o sin ningún cruce resuelto, conserve el
# esquema en vez de quedarse sin columnas.
COLONIA_FIELDS = [
    "post_id",
    "location_type",
    "raw_text",
    "colonia_id",
    "source_field",
    "match_method",
]
CROSSING_FIELDS = [
    "post_id",
    "location_type",
    "raw_text",
    "source_field",
    "geometry",
    "match_method",
]


def find_colonias(haystack: str, pattern: re.Pattern) -> dict[str, bool]:
    """Nombres del catálogo en el texto, y si venían con marcador de colonia."""
    found: dict[str, bool] = {}
    for match in pattern.finditer(haystack):
        name = match.group(1)
        if name in INSTITUTIONAL:
            continue
        before = haystack[max(0, match.start() - MARKER_LOOKBEHIND) : match.start()]
        if STREET_MARKER.search(before):
            continue
        found[name] = found.get(name, False) or bool(COLONIA_MARKER.search(before))
    return found


def build_colonia_mentions(posts: pd.DataFrame, colonias: pd.DataFrame) -> list[dict]:
    catalog = (
        colonias[["colonia_id", "settlement_name_normalized"]]
        .drop_duplicates("settlement_name_normalized")
        .set_index("settlement_name_normalized")["colonia_id"]
    )
    searchable = sorted(name for name in catalog.index if len(name) >= MIN_NAME_LENGTH)
    pattern = re.compile(r"\b(" + "|".join(re.escape(n) for n in searchable) + r")\b")

    # Por separado en el cuerpo y en el OCR, para poder decir de dónde salió cada mención.
    post_texts = posts["text"].fillna("").map(normalize_name)
    ocr_texts = posts["ocr_text"].fillna("").map(normalize_name)

    mentions = []
    for post_id, post_text, ocr_text in zip(posts["post_id"], post_texts, ocr_texts):
        in_post = find_colonias(post_text, pattern)
        in_ocr = find_colonias(ocr_text, pattern)
        for name in in_post.keys() | in_ocr.keys():
            has_marker = in_post.get(name, False) or in_ocr.get(name, False)
            mentions.append(
                {
                    "post_id": post_id,
                    "location_type": "colonia",
                    "raw_text": name,
                    "colonia_id": catalog[name],
                    "source_field": (
                        "ambos"
                        if name in in_post and name in in_ocr
                        else ("texto" if name in in_post else "ocr")
                    ),
                    "match_method": (
                        "colonia_con_marcador" if has_marker else "colonia_en_catalogo"
                    ),
                }
            )
    return mentions


def extract_crossings(posts: pd.DataFrame) -> pd.DataFrame:
    mentions = []
    for post_id, post_text, ocr_text in zip(
        posts["post_id"], posts["text"].fillna(""), posts["ocr_text"].fillna("")
    ):
        for source, text in (("texto", post_text), ("ocr", ocr_text)):
            for found in CROSSING_PATTERN.finditer(text):
                mentions.append(
                    {
                        "post_id": post_id,
                        "expression": found.group(1).strip(),
                        "source_field": source,
                    }
                )
    columns = ["post_id", "expression", "source_field"]
    return pd.DataFrame(mentions, columns=columns).drop_duplicates(["post_id", "expression"])


def locate_crossings(
    crossings: pd.DataFrame, streets: StreetIndex, colonias: gpd.GeoDataFrame
) -> gpd.GeoDataFrame:
    located = []
    for row in crossings.itertuples():
        points = streets.locate_expression(row.expression)
        common = {
            "post_id": row.post_id,
            "location_type": "cruce",
            "raw_text": row.expression,
            "source_field": row.source_field,
        }
        if not points:
            located.append({**common, "geometry": None, "match_method": "unmatched"})
            continue
        # Varios cruces posibles (la misma pareja de calles se toca en más de un lugar):
        # nos quedamos con su centro, que es lo que el aviso quiere decir.
        center = gpd.GeoSeries([point for point, _ in points]).union_all().centroid
        located.append({**common, "geometry": center, "match_method": "cruce_geocodificado"})

    points_gdf = gpd.GeoDataFrame(
        pd.DataFrame(located, columns=CROSSING_FIELDS), geometry="geometry", crs=colonias.crs
    )
    resolved = points_gdf[points_gdf["geometry"].notna()].copy()
    unresolved = points_gdf[points_gdf["geometry"].isna()].copy()

    if resolved.empty:
        # Ningún cruce se pudo ubicar: sjoin_nearest no tiene con qué trabajar.
        with_colonia = resolved.assign(colonia_id=None, lat=None, lon=None)
    else:
        with_colonia = gpd.sjoin_nearest(
            resolved, colonias[["colonia_id", "geometry"]], how="left"
        ).drop(columns="index_right")
        # sjoin_nearest duplica el punto si empata con dos colonias: nos quedamos con una.
        with_colonia = with_colonia[~with_colonia.index.duplicated()]

        geographic = with_colonia.geometry.to_crs(epsg=GEOGRAPHIC)
        with_colonia["lat"] = geographic.y.round(6)
        with_colonia["lon"] = geographic.x.round(6)

    for column in ("colonia_id", "lat", "lon"):
        unresolved[column] = None

    return pd.concat([with_colonia, unresolved], ignore_index=True).drop(columns="geometry")


def build_ubicaciones(
    posts: pd.DataFrame, colonias: gpd.GeoDataFrame, streets: StreetIndex
) -> pd.DataFrame:
    colonia_rows = pd.DataFrame(build_colonia_mentions(posts, colonias), columns=COLONIA_FIELDS)
    # Una colonia mencionada no es un punto, es su polígono: quien lo quiera dibujar une por
    # colonia_id contra colonias_hermosillo. Ponerle aquí el centroide apilaría cientos de
    # menciones en una sola coordenada y fabricaría focos donde no los hay.
    colonia_rows["lat"] = pd.NA
    colonia_rows["lon"] = pd.NA

    crossing_rows = locate_crossings(extract_crossings(posts), streets, colonias)

    locations = pd.concat([colonia_rows[COLUMNS], crossing_rows[COLUMNS]], ignore_index=True)
    # El texto extraído a veces arrastra una palabra de más ("... y De las Rocas Col"), lo
    # que produce dos filas para el mismo cruce. Se resuelven al mismo punto, así que
    # deduplicamos por ubicación. Solo aplica a los cruces: las menciones de colonia ya son
    # únicas por publicación.
    repeated = (
        locations["location_type"].eq("cruce")
        & locations["lat"].notna()
        & locations.duplicated(subset=["post_id", "location_type", "lat", "lon"])
    )
    locations = locations[~repeated]
    return locations.sort_values(["post_id", "location_type", "raw_text"]).reset_index(drop=True)


@log_execution
def process_ubicaciones_aviso(params: dict) -> None:
    mg = load_dataset_config(params, source="inegi", dataset="mg_2025_sonora")
    posts_dataset = load_dataset_config(
        params, source="agua_hermosillo", dataset="publicaciones_aguah"
    )
    dcah = load_dataset_config(params, source="inegi", dataset="dcah_2025")
    dataset = load_dataset_config(params, source="agua_hermosillo", dataset="ubicaciones_aviso")

    posts_file = (
        Path(posts_dataset["processed"]["directory"]) / posts_dataset["processed"]["filename"]
    )
    # Las colonias se reconstruyen del shapefile, no del GeoPackage ya publicado: pasar la
    # geometría por coordenadas geográficas y de vuelta movía puntos lo suficiente para
    # cambiar de colonia en los cruces que caen justo en un límite.
    settlements_file = Path(dcah["interim"]["directory"]) / "conjunto_de_datos" / "26as.shp"
    streets_file = Path(mg["raw"]["directory"]) / "26e.shp"

    for required in (posts_file, settlements_file, streets_file):
        if not required.exists():
            raise FileNotFoundError(f"{required} not found: run `make data` first")

    posts = pd.read_csv(posts_file)
    colonias = build_colonias(gpd.read_file(settlements_file))
    streets = StreetIndex(read_city_streets(streets_file, *HERMOSILLO_CITY))
    logger.info("Read {} publications and {} settlements", len(posts), len(colonias))

    locations = build_ubicaciones(posts, colonias, streets)
    resolved = locations["match_method"].ne("unmatched")
    logger.info("Located {} of {} mentions", int(resolved.sum()), len(locations))

    processed_dir = Path(dataset["processed"]["directory"])
    processed_dir.mkdir(parents=True, exist_ok=True)
    processed_file = processed_dir / dataset["processed"]["filename"]
    locations.to_csv(processed_file, index=False)
    logger.info("Wrote processed data → {}", processed_file)


if __name__ == "__main__":
    params = load_params()

    load_logging(
        level=params["logging"]["level"],
        log_file=Path(params["logging"]["file"]),
        console=params["logging"].get("console", False),
    )

    process_ubicaciones_aviso(params)
