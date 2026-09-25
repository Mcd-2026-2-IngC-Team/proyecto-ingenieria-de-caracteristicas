"""Ubicar cruces de calles de los avisos sobre los ejes de vialidad del INEGI.

Todo trabaja en EPSG:6372 (Lambert sobre ITRF2008), donde las distancias son metros. No
hay tabla de correcciones a mano: lo que las reglas generales no resuelven queda sin
resolver, y esa cobertura es un resultado del análisis.
"""

import difflib
import re

import geopandas as gpd
from loguru import logger

from project_name.text import normalize_name

# Proyección métrica del INEGI. El .prj de la capa de calles se llama
# MEXICO_ITRF_2008_LCC y geopandas no le reconoce EPSG, así que hay que forzarla.
LAMBERT_MEXICO = 6372
# Coordenadas geográficas, que es lo que se publica para dibujar.
GEOGRAPHIC = 4326
HERMOSILLO = "030"

ARTICLES = ("DE LOS ", "DE LAS ", "DE LA ", "DEL ", "LOS ", "LAS ", "LA ", "EL ")
# El aviso escribe "Blvr. Luis Donaldo Colosio"; el INEGI guarda el nombre en NOMVIAL y el
# tipo aparte, en TIPOVIAL, así que el tipo estorba al buscar.
TYPE_PREFIX = re.compile(
    r"^(?:CALLE|BULEVAR|BLVR|BLVD|AVENIDA|AVE|AV|CAMINO|CARRETERA|PERIFERICO"
    r"|PROLONGACION|RETORNO|CALLEJON)\s+"
)
# El aviso escribe "calle Dos" y el INEGI "2".
NUMBER_WORDS = {
    "UNO": "1", "DOS": "2", "TRES": "3", "CUATRO": "4", "CINCO": "5",
    "SEIS": "6", "SIETE": "7", "OCHO": "8", "NUEVE": "9", "DIEZ": "10",
}  # fmt: skip
CROSSING_FORMS = (
    # "A entre B y C" es el tramo de A entre sus dos cruces; los otros son un cruce.
    r"(.+?) entre (.+?) y (.+)$",
    r"(.+?) entre (.+)$",
    r"(.+?) y (.+)$",
)
CROSSING_TOLERANCE_M = 50.0
OCR_SIMILARITY = 0.85


def read_city_streets(streets_file, municipality: str, locality: str) -> gpd.GeoDataFrame:
    streets = gpd.read_file(streets_file).to_crs(epsg=LAMBERT_MEXICO)
    city = streets[(streets["CVE_MUN"] == municipality) & (streets["CVE_LOC"] == locality)].copy()
    city["street_key"] = city["NOMVIAL"].map(normalize_name)
    return city[["street_key", "geometry"]]


class StreetIndex:
    """Busca calles por nombre y ubica el cruce entre dos de ellas."""

    def __init__(self, city_streets: gpd.GeoDataFrame):
        self.city_streets = city_streets
        self.street_names = sorted(city_streets["street_key"].unique())
        self._cache: dict[str, frozenset] = {}

    def _matching_streets(self, key: str) -> set:
        # Calles que contienen el nombre buscado como palabra completa: el aviso dice
        # "Mariano Escobedo" y la cartografía "General Mariano Escobedo".
        key = NUMBER_WORDS.get(key, key)
        variants = {key} | {key.removeprefix(a) for a in ARTICLES if key.startswith(a)}
        return {
            n
            for n in self.street_names
            for v in variants
            if v and re.search(rf"\b{re.escape(v)}\b", n)
        }

    def candidates(self, name: str) -> frozenset:
        key = TYPE_PREFIX.sub("", normalize_name(name))
        if key in self._cache:
            return self._cache[key]
        # No sabemos dónde termina el nombre dentro de la frase, así que probamos del más
        # largo al más corto y dejamos que la cartografía decida: gana el primer prefijo
        # que existe. Eso evita adivinar la frontera con una regla de puntuación.
        words = key.split()
        found = set()
        for cut in range(len(words), 0, -1):
            found = self._matching_streets(" ".join(words[:cut]))
            if found:
                break
        # Si nada coincide, toleramos errores del OCR ("Carcia" -> "García").
        if not found:
            found = set(
                difflib.get_close_matches(key, self.street_names, n=1, cutoff=OCR_SIMILARITY)
            )
        self._cache[key] = frozenset(found)
        return self._cache[key]

    def _segments(self, keys: frozenset) -> gpd.GeoDataFrame:
        return self.city_streets.loc[self.city_streets["street_key"].isin(keys), ["geometry"]]

    def crossing_points(
        self, first: frozenset, second: frozenset, tolerance_m: float = CROSSING_TOLERANCE_M
    ) -> list:
        """Puntos donde se encuentran las dos calles, con su separación en metros.

        El cruce es el punto medio de la línea más corta entre los tramos más cercanos: si
        las calles se cruzan de verdad esa línea mide 0 y su punto medio es la intersección.
        La tolerancia cubre calles que en la cartografía no comparten nodo, y es menor a
        media cuadra para no confundir paralelas.
        """
        if not first or not second:
            return []
        segments_b = self._segments(second)
        if segments_b.empty:
            return []
        pairs = gpd.sjoin_nearest(
            self._segments(first), segments_b, max_distance=tolerance_m, distance_col="gap_m"
        )
        if pairs.empty:
            return []
        gap = pairs["gap_m"].min()
        closest = pairs[pairs["gap_m"] <= gap + 0.01]
        links = closest.geometry.shortest_line(
            segments_b.geometry.loc[closest["index_right"]], align=False
        )
        midpoints = links.interpolate(0.5, normalized=True)
        # Dos tramos que llegan al mismo nodo dan el mismo cruce: se cuenta una vez.
        midpoints = midpoints[~midpoints.set_precision(0.1).duplicated()]
        return [(point, gap) for point in midpoints]

    def locate_expression(self, expression: str) -> list:
        """Ubica "A entre B y C", "A entre B" o "A y B"."""
        parsed = next(
            (m for form in CROSSING_FORMS if (m := re.match(form, expression, re.IGNORECASE))),
            None,
        )
        if not parsed:
            return []
        main, *crosses = parsed.groups()
        main_keys = self.candidates(main)
        return [
            point
            for cross in crosses
            for point in self.crossing_points(main_keys, self.candidates(cross))
        ]


def build_colonias(settlements: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """Asentamientos de Hermosillo del DCAH, con su centroide en coordenadas geográficas."""
    city = settlements[settlements["cve_mun"] == HERMOSILLO].copy()

    # Dos polígonos del DCAH (Palo Verde y Sahuaro) se cruzan consigo mismos, un defecto
    # común en la cartografía catastral. Repararlos no cambia el área pero evita que
    # fallen el punto en polígono y el dibujado.
    invalid = int((~city.geometry.is_valid).sum())
    if invalid:
        logger.info("Repairing {} invalid polygons", invalid)
        city["geometry"] = city.geometry.make_valid()

    # El área se calcula en la proyección métrica original; el centroide se publica en
    # coordenadas geográficas, que es lo que el tablero dibuja.
    centroids = city.geometry.centroid.to_crs(epsg=GEOGRAPHIC)

    return gpd.GeoDataFrame(
        {
            "colonia_id": city["cvegeo"],
            "settlement_name": city["nom_asen"],
            "settlement_name_normalized": city["nom_asen"].map(normalize_name),
            "settlement_type": city["tipo"],
            "locality_code": city["cve_loc"],
            "postal_code": city["cp"],
            "area_km2": (city.geometry.area / 1e6).round(4),
            "centroid_lat": centroids.y.round(6),
            "centroid_lon": centroids.x.round(6),
            "updated_at": city["fecha_act"],
            "geometry": city.geometry,
        },
        crs=city.crs,
    ).reset_index(drop=True)
