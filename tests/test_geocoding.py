import geopandas as gpd
import pytest
from shapely.geometry import LineString, Polygon

from project_name.geocoding import LAMBERT_MEXICO, StreetIndex, build_colonias

# Traza mínima en metros: Escobedo corre de este a oeste y las demás la cruzan.
STREETS = {
    "GENERAL MARIANO ESCOBEDO": LineString([(0, 0), (200, 0)]),
    "ROSALES": LineString([(50, -50), (50, 50)]),
    "2": LineString([(120, -50), (120, 50)]),
    # Termina 30 m antes de Escobedo: la cartografía no cierra el nodo.
    "SEPARADA": LineString([(160, -50), (160, -30)]),
    "LEJANA": LineString([(0, 5000), (200, 5000)]),
}


@pytest.fixture
def streets() -> StreetIndex:
    frame = gpd.GeoDataFrame(
        {"street_key": list(STREETS), "geometry": list(STREETS.values())},
        crs=LAMBERT_MEXICO,
    )
    return StreetIndex(frame)


def test_candidates_matches_a_street_named_more_fully(streets):
    # El aviso dice "Mariano Escobedo" y la cartografía "General Mariano Escobedo".
    assert streets.candidates("Mariano Escobedo") == frozenset({"GENERAL MARIANO ESCOBEDO"})


def test_candidates_ignores_the_street_type_written_by_the_notice(streets):
    # El INEGI guarda el tipo aparte, en TIPOVIAL, así que estorba al buscar.
    assert streets.candidates("calle Rosales") == frozenset({"ROSALES"})
    assert streets.candidates("Blvr. Rosales") == frozenset({"ROSALES"})


def test_candidates_translates_number_words(streets):
    # El aviso escribe "calle Dos" y el INEGI "2".
    assert streets.candidates("calle Dos") == frozenset({"2"})


def test_candidates_tolerates_ocr_typos(streets):
    assert streets.candidates("Rosalez") == frozenset({"ROSALES"})


def test_candidates_returns_nothing_for_an_unknown_street(streets):
    assert streets.candidates("Calle Que No Existe Aqui") == frozenset()


def test_crossing_points_returns_the_intersection_when_streets_touch(streets):
    points = streets.crossing_points(streets.candidates("Escobedo"), streets.candidates("Rosales"))

    assert len(points) == 1
    point, gap = points[0]
    assert gap == 0
    assert (round(point.x), round(point.y)) == (50, 0)


def test_crossing_points_bridges_streets_that_do_not_share_a_node(streets):
    """Sin nodo común, el punto es el medio de la separación: no cae sobre ninguna calle."""
    points = streets.crossing_points(
        streets.candidates("Escobedo"), streets.candidates("Separada")
    )

    assert len(points) == 1
    point, gap = points[0]
    assert gap == pytest.approx(30.0)
    assert (round(point.x), round(point.y)) == (160, -15)


def test_crossing_points_ignores_streets_beyond_the_tolerance(streets):
    assert (
        streets.crossing_points(streets.candidates("Escobedo"), streets.candidates("Lejana")) == []
    )


def test_locate_expression_reads_a_plain_crossing(streets):
    ((point, _),) = streets.locate_expression("Escobedo y Rosales")

    assert (round(point.x), round(point.y)) == (50, 0)


def test_locate_expression_reads_a_stretch_between_two_crossings(streets):
    # "A entre B y C" son los dos extremos del tramo, no un solo punto.
    points = streets.locate_expression("Escobedo entre Rosales y Dos")

    assert sorted(round(point.x) for point, _ in points) == [50, 120]


def test_locate_expression_returns_nothing_without_a_crossing_form(streets):
    assert streets.locate_expression("Escobedo") == []


def test_build_colonias_repairs_self_intersecting_polygons():
    """Dos polígonos del DCAH vienen cruzados consigo mismos; repararlos no cambia el área."""
    bowtie = Polygon([(0, 0), (10, 10), (10, 0), (0, 10)])
    settlements = gpd.GeoDataFrame(
        {
            "cve_mun": ["030"],
            "cvegeo": ["2603000010001"],
            "nom_asen": ["Y Griega"],
            "tipo": ["BARRIO"],
            "cve_loc": ["0001"],
            "cp": ["83290"],
            "fecha_act": ["11/2025"],
            "geometry": [bowtie],
        },
        crs=LAMBERT_MEXICO,
    )
    assert not settlements.geometry.is_valid.all()

    colonias = build_colonias(settlements)

    assert colonias.geometry.is_valid.all()
    assert colonias.loc[0, "settlement_name_normalized"] == "Y GRIEGA"


def test_build_colonias_keeps_only_hermosillo():
    others = gpd.GeoDataFrame(
        {
            "cve_mun": ["030", "018"],
            "cvegeo": ["2603000010001", "2601800010001"],
            "nom_asen": ["Centro", "Otra"],
            "tipo": ["COLONIA", "COLONIA"],
            "cve_loc": ["0001", "0001"],
            "cp": ["83000", "84000"],
            "fecha_act": ["11/2025", "11/2025"],
            "geometry": [Polygon([(0, 0), (1, 0), (1, 1)]), Polygon([(5, 5), (6, 5), (6, 6)])],
        },
        crs=LAMBERT_MEXICO,
    )

    colonias = build_colonias(others)

    assert list(colonias["settlement_name"]) == ["Centro"]
