import geopandas as gpd
import pandas as pd
from shapely.geometry import LineString, box

from project_name import hydro_context as hc

CRS = hc.METRIC_CRS


def make_colonias() -> gpd.GeoDataFrame:
    # Dos colonias de 100 m de lado; sus centroides quedan en (50, 50) y (1050, 50).
    return gpd.GeoDataFrame(
        {"colonia_id": ["A", "B"]},
        geometry=[box(0, 0, 100, 100), box(1000, 0, 1100, 100)],
        crs=CRS,
    )


def make_streams() -> gpd.GeoDataFrame:
    # Cuatro tramos verticales en x = 150, 300, 600 y 1200.
    xs = [150, 300, 600, 1200]
    return gpd.GeoDataFrame(
        {
            "ID": [11, 12, 13, 14],
            "ORDER_1": [3, 1, -1, 2],
            "LEVEL_1": [1, 4, -1, 3],
            "ENABLED": [1, 1, 0, 1],
        },
        geometry=[LineString([(x, -500), (x, 500)]) for x in xs],
        crs=CRS,
    )


def test_nearest_segments_orders_by_distance_from_the_centroid():
    segments = hc.nearest_segments(make_colonias(), make_streams())

    assert segments.loc["A", ["id_seg_1", "id_seg_2", "id_seg_3"]].tolist() == [11, 12, 13]
    assert segments.loc["A", "dist_seg_1"] == 100
    assert segments.loc["A", "dist_seg_3"] == 550
    assert segments.loc["B", "id_seg_1"] == 14
    assert segments.loc["B", "dist_seg_1"] == 150


def test_segment_features_skip_disabled_segments():
    streams = make_streams()
    segments = hc.nearest_segments(make_colonias(), streams)

    features = hc.segment_features(segments, streams)

    # El tramo 13 (ENABLED = 0, códigos -1) no entra en las estadísticas de A.
    assert features.loc["A", "order_max"] == 3
    assert features.loc["A", "level_min"] == 1
    assert features.loc["A", "order_median"] == 2


def test_relabel_by_profile_gives_the_report_names_whatever_the_raw_labels():
    frame = pd.DataFrame(
        {
            # Perfiles: lejano, colector, arroyo de cabecera y el más cercano.
            "order_median": [1.0, 3.5, 1.2, 1.3],
            "order_max": [1.0, 4.0, 1.5, 2.0],
            "level_median": [3.0, 1.5, 4.8, 2.7],
            "level_min": [3.0, 1.0, 4.0, 2.0],
            "proximity_ord": [2.0, 0.5, 0.3, 0.2],
        }
    )
    raw_labels = pd.Series([7, 2, 5, 9])

    assert hc.relabel_by_profile(frame, raw_labels).tolist() == [0, 1, 2, 3]
