import geopandas as gpd
import pandas as pd
from shapely.geometry import LineString, Polygon

from project_name.geocoding import LAMBERT_MEXICO, StreetIndex
from project_name.jobs.process_ubicaciones_aviso_job import (
    build_colonia_mentions,
    build_ubicaciones,
    extract_crossings,
)

COLONIAS = gpd.GeoDataFrame(
    {
        "colonia_id": ["2603000010001", "2603000010002", "2603000010003"],
        "settlement_name": ["Centro", "Luis Encinas", "H. Ayuntamiento"],
        "settlement_name_normalized": ["CENTRO", "LUIS ENCINAS", "H AYUNTAMIENTO"],
        "geometry": [
            Polygon([(0, 0), (200, 0), (200, 200), (0, 200)]),
            Polygon([(300, 0), (400, 0), (400, 100), (300, 100)]),
            Polygon([(500, 0), (600, 0), (600, 100), (500, 100)]),
        ],
    },
    crs=LAMBERT_MEXICO,
)
STREETS = StreetIndex(
    gpd.GeoDataFrame(
        {
            "street_key": ["ROSALES", "MINA"],
            "geometry": [
                LineString([(0, 100), (200, 100)]),
                LineString([(100, 0), (100, 200)]),
            ],
        },
        crs=LAMBERT_MEXICO,
    )
)


def make_posts(text: str = "", ocr_text: str = "") -> pd.DataFrame:
    return pd.DataFrame([{"post_id": 1, "text": text, "ocr_text": ocr_text}])


def mention_names(posts: pd.DataFrame) -> list[str]:
    return [m["raw_text"] for m in build_colonia_mentions(posts, COLONIAS)]


def test_finds_a_colonia_named_in_the_text():
    assert mention_names(make_posts("afectación en la colonia Centro")) == ["CENTRO"]


def test_marks_whether_the_name_came_with_a_colonia_marker():
    with_marker = build_colonia_mentions(make_posts("la colonia Centro"), COLONIAS)
    bare = build_colonia_mentions(make_posts("CENTRO"), COLONIAS)

    assert with_marker[0]["match_method"] == "colonia_con_marcador"
    assert bare[0]["match_method"] == "colonia_en_catalogo"


def test_ignores_a_name_that_is_really_a_street():
    """En Hermosillo hay colonias que se llaman igual que los bulevares principales."""
    assert mention_names(make_posts("fuga sobre bulevar Luis Encinas")) == []
    assert mention_names(make_posts("en la colonia Luis Encinas")) == ["LUIS ENCINAS"]


def test_ignores_the_city_government():
    # "H. Ayuntamiento de Hermosillo" es la institución, no la colonia homónima.
    assert mention_names(make_posts("en coordinación con el H. Ayuntamiento")) == []


def test_records_where_the_mention_was_found():
    both = build_colonia_mentions(make_posts("colonia Centro", "COLONIA CENTRO"), COLONIAS)
    only_flyer = build_colonia_mentions(make_posts("", "COLONIA CENTRO"), COLONIAS)

    assert both[0]["source_field"] == "ambos"
    assert only_flyer[0]["source_field"] == "ocr"


def test_extracts_a_crossing_from_the_text():
    crossings = extract_crossings(make_posts("reparación en calle Rosales y Mina"))

    assert list(crossings["expression"]) == ["Rosales y Mina"]


def test_crossing_name_is_bounded_to_a_few_words():
    """Un nombre de calle son pocas palabras: el tope evita tragarse la oración entera.

    El tope es de cuatro palabras, así que en prosa corrida todavía arrastra algunas de
    más ("Mina registrada la mañana"). Eso no estorba al geocodificar, porque la búsqueda
    prueba del prefijo más largo al más corto y gana el primero que existe en la
    cartografía, pero sí deja `raw_text` con cola.
    """
    crossings = extract_crossings(
        make_posts("fuga en calle Rosales y Mina registrada la mañana de este martes")
    )

    expression = crossings.loc[0, "expression"]
    assert expression.startswith("Rosales y Mina")
    assert "de este martes" not in expression


def test_crossing_never_crosses_a_line_break():
    # Los volantes traen una calle por renglón: cruzar el salto uniría calles distintas.
    crossings = extract_crossings(make_posts("calle Rosales y Mina\nOtra Colonia Afectada"))

    assert "Otra" not in crossings.loc[0, "expression"]


def test_build_ubicaciones_geocodes_the_crossing_and_assigns_its_colonia():
    posts = make_posts("fuga en calle Rosales y Mina")

    locations = build_ubicaciones(posts, COLONIAS, STREETS)
    crossing = locations[locations["location_type"] == "cruce"].iloc[0]

    assert crossing["match_method"] == "cruce_geocodificado"
    assert crossing["colonia_id"] == "2603000010001"
    assert crossing["lat"] and crossing["lon"]


def test_build_ubicaciones_keeps_the_crossings_it_cannot_resolve():
    # Sin las filas sin resolver la cobertura parecería del 100%.
    posts = make_posts("fuga en calle Inexistente y Tampoco")

    locations = build_ubicaciones(posts, COLONIAS, STREETS)

    assert list(locations["match_method"]) == ["unmatched"]


def test_build_ubicaciones_leaves_colonia_rows_without_a_point():
    """Una colonia es un polígono: darle el centroide apilaría menciones en un punto."""
    posts = make_posts("afectación en la colonia Centro")

    locations = build_ubicaciones(posts, COLONIAS, STREETS)
    colonia = locations[locations["location_type"] == "colonia"].iloc[0]

    assert pd.isna(colonia["lat"])
    assert pd.isna(colonia["lon"])
