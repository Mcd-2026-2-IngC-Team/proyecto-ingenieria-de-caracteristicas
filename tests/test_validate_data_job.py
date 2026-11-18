from pathlib import Path

from loguru import logger
import pandas as pd
import pytest

from project_name.jobs import validate_data_job as job
from project_name.schemas import REACTIONS


@pytest.fixture
def messages():
    captured = []
    sink = logger.add(captured.append, format="{message}")
    yield captured
    logger.remove(sink)


def make_params(tmp_path: Path, *datasets: str) -> dict:
    return {
        "sources": {
            "agua_hermosillo": {
                "datasets": {
                    dataset: {
                        "processed": {"directory": str(tmp_path), "filename": f"{dataset}.csv"}
                    }
                    for dataset in datasets
                }
            }
        }
    }


def make_colonias(**overrides) -> pd.DataFrame:
    colonias = pd.DataFrame(
        {
            "colonia_id": ["2603000010001", "2603000010002"],
            "settlement_name": ["Centro", "Pitic"],
            "settlement_name_normalized": ["CENTRO", "PITIC"],
            "settlement_type": ["COLONIA", "COLONIA"],
            "locality_code": ["0001", "0001"],
            "postal_code": ["83000", "83150"],
            "area_km2": [1.2, 0.8],
            "centroid_lat": [29.07, 29.09],
            "centroid_lon": [-110.95, -110.96],
            "updated_at": ["11/2025", "11/2025"],
        }
    )
    return colonias.assign(**overrides)


def make_ubicaciones(**overrides) -> pd.DataFrame:
    ubicaciones = pd.DataFrame(
        {
            "post_id": [1, 2],
            "location_type": ["colonia", "cruce"],
            "raw_text": ["CENTRO", "ROSALES Y ESCOBEDO"],
            "colonia_id": ["2603000010001", "2603000010002"],
            "source_field": ["texto", "ocr"],
            "lat": [None, 29.07],
            "lon": [None, -110.95],
            "match_method": ["colonia_con_marcador", "cruce_geocodificado"],
        }
    )
    return ubicaciones.assign(**overrides)


def test_validate_data_accepts_valid_colonias_keeping_leading_zeros(tmp_path, messages):
    make_colonias().to_csv(tmp_path / "colonias_hermosillo.csv", index=False)

    job.validate_data(make_params(tmp_path, "colonias_hermosillo"))

    assert "colonias_hermosillo: 2 rows pass the quality rules" in "".join(messages)


def test_validate_data_reports_every_broken_rule(tmp_path, messages):
    broken = make_colonias(colonia_id=["2603000010001"] * 2, postal_code=["83000", "8315"])
    broken.to_csv(tmp_path / "colonias_hermosillo.csv", index=False)

    with pytest.raises(ValueError, match="colonias_hermosillo"):
        job.validate_data(make_params(tmp_path, "colonias_hermosillo"))

    log = "".join(messages)
    assert "colonia_id failed field_uniqueness" in log
    assert "postal_code failed str_matches" in log


def test_validate_data_rejects_values_outside_a_closed_catalog(tmp_path, messages):
    broken = make_ubicaciones(match_method=["colonia_con_marcador", "adivinado"])
    broken.to_csv(tmp_path / "ubicaciones_aviso.csv", index=False)

    with pytest.raises(ValueError, match="ubicaciones_aviso"):
        job.validate_data(make_params(tmp_path, "ubicaciones_aviso"))

    assert "['adivinado']" in "".join(messages)


def test_validate_data_accepts_nulls_explained_by_match_method(tmp_path, messages):
    unresolved = pd.DataFrame(
        {
            "post_id": [3],
            "location_type": ["cruce"],
            "raw_text": ["INEXISTENTE Y TAMPOCO"],
            "colonia_id": [None],
            "source_field": ["texto"],
            "lat": [None],
            "lon": [None],
            "match_method": ["unmatched"],
        }
    )
    pd.concat([make_ubicaciones(), unresolved]).to_csv(
        tmp_path / "ubicaciones_aviso.csv", index=False
    )

    job.validate_data(make_params(tmp_path, "ubicaciones_aviso"))

    assert "ubicaciones_aviso: 3 rows pass the quality rules" in "".join(messages)


def test_validate_data_rejects_a_geocoded_crossing_without_point(tmp_path, messages):
    broken = make_ubicaciones(lat=[None, None])
    broken.to_csv(tmp_path / "ubicaciones_aviso.csv", index=False)

    with pytest.raises(ValueError, match="ubicaciones_aviso"):
        job.validate_data(make_params(tmp_path, "ubicaciones_aviso"))

    assert "point_only_for_geocoded_crossings" in "".join(messages)


def test_validate_data_rejects_a_colonia_mention_with_a_point(tmp_path, messages):
    # Una colonia es un polígono: si trae punto, alguien le puso su centroide.
    broken = make_ubicaciones(lat=[29.08, 29.07], lon=[-110.95, -110.95])
    broken.to_csv(tmp_path / "ubicaciones_aviso.csv", index=False)

    with pytest.raises(ValueError, match="ubicaciones_aviso"):
        job.validate_data(make_params(tmp_path, "ubicaciones_aviso"))

    assert "point_only_for_geocoded_crossings" in "".join(messages)


def test_validate_data_skips_datasets_without_rules(tmp_path, messages):
    pd.DataFrame({"id": [1]}).to_csv(tmp_path / "sin_reglas.csv", index=False)

    job.validate_data(make_params(tmp_path, "sin_reglas"))

    assert "No quality rules for sin_reglas, skipped" in "".join(messages)


def make_publicaciones(**overrides) -> pd.DataFrame:
    """Una publicación sin texto ni OCR ni comentario: los tres quedan vacíos."""
    reactions = {f"reactions_{name}": [0] for name in REACTIONS if name != "angry"}
    publicaciones = pd.DataFrame(
        {
            "post_id": [1],
            "published_at": ["2024-08-15 12:30:00"],
            "year": [2024],
            "month": [8],
            "iso_week": [33],
            "day_of_week": [3],
            "hour_of_day": [12],
            "text": [""],
            "has_text": [False],
            "ocr_text": [""],
            "has_ocr_text": [False],
            "ocr_status": ["skipped_no_image"],
            **reactions,
            "reactions_angry": [2],
            "reactions_total": [2],
            "angry_share": [1.0],
            "comments_count": [0],
            "shares_count": [0],
            "likes_count": [0],
            "top_comment_text": [""],
            "top_comment_likes": [0],
            "event_type": ["otro"],
            "announced_start_at": [None],
            "has_announced_start_at": [False],
            "announced_duration_hours": [None],
        }
    )
    return publicaciones.assign(**overrides)


def test_validate_data_reads_empty_texts_as_empty_not_null(tmp_path, messages):
    make_publicaciones().to_csv(tmp_path / "publicaciones_aguah.csv", index=False)

    job.validate_data(make_params(tmp_path, "publicaciones_aguah"))

    assert "publicaciones_aguah: 1 rows pass the quality rules" in "".join(messages)


def test_validate_data_rejects_flags_that_contradict_their_column(tmp_path, messages):
    broken = make_publicaciones(has_ocr_text=[True])
    broken.to_csv(tmp_path / "publicaciones_aguah.csv", index=False)

    with pytest.raises(ValueError, match="publicaciones_aguah"):
        job.validate_data(make_params(tmp_path, "publicaciones_aguah"))

    assert "has_ocr_text_matches_ocr_text" in "".join(messages)


def make_llamadas(**overrides) -> pd.DataFrame:
    """Una llamada ubicada por catálogo y otra sin colonia."""
    llamadas = pd.DataFrame(
        {
            "colonia": ["CENTRO", "SIN COLONIA"],
            "tipo_incidente": ["INUNDACIONES", "ALCANTARILLA SIN TAPA"],
            "fecha": ["2024-08-15", "2024-08-16"],
            "hora": [21, 3],
            "grupo_incidente": ["inundacion_directa", "drenaje_y_red_de_agua"],
            "colonia_id": ["2603000010001", None],
            "colonia_source": ["catalogo", None],
        }
    )
    return llamadas.assign(**overrides)


def test_validate_data_accepts_valid_llamadas_911(tmp_path, messages):
    make_llamadas().to_csv(tmp_path / "llamadas_911_hermosillo.csv", index=False)

    job.validate_data(make_params(tmp_path, "llamadas_911_hermosillo"))

    assert "llamadas_911_hermosillo: 2 rows pass the quality rules" in "".join(messages)


def test_validate_data_rejects_a_spelling_variant_of_tipo_incidente(tmp_path, messages):
    # "INUNDACIÓN" se unifica a "INUNDACIONES" en process_llamadas_911_job.
    broken = make_llamadas(tipo_incidente=["INUNDACIÓN", "ALCANTARILLA SIN TAPA"])
    broken.to_csv(tmp_path / "llamadas_911_hermosillo.csv", index=False)

    with pytest.raises(ValueError, match="llamadas_911_hermosillo"):
        job.validate_data(make_params(tmp_path, "llamadas_911_hermosillo"))

    assert "['INUNDACIÓN']" in "".join(messages)


def test_validate_data_rejects_a_tipo_in_the_wrong_group(tmp_path, messages):
    broken = make_llamadas(grupo_incidente=["terreno", "drenaje_y_red_de_agua"])
    broken.to_csv(tmp_path / "llamadas_911_hermosillo.csv", index=False)

    with pytest.raises(ValueError, match="llamadas_911_hermosillo"):
        job.validate_data(make_params(tmp_path, "llamadas_911_hermosillo"))

    assert "tipo_incidente_in_its_group" in "".join(messages)


def test_validate_data_rejects_an_hour_outside_the_day(tmp_path, messages):
    broken = make_llamadas(hora=[24, 3])
    broken.to_csv(tmp_path / "llamadas_911_hermosillo.csv", index=False)

    with pytest.raises(ValueError, match="llamadas_911_hermosillo"):
        job.validate_data(make_params(tmp_path, "llamadas_911_hermosillo"))

    assert "hora failed in_range" in "".join(messages)


def make_precipitacion(**overrides) -> pd.DataFrame:
    precipitacion = pd.DataFrame(
        {
            "date": ["2024-08-15", "2024-08-16"],
            "precipitation_mm": [12.5, 0.4],
            "precipitation_hours": [3.0, 1.0],
            "year": [2024, 2024],
            "month": [8, 8],
            "is_rain_day": [True, False],
        }
    )
    return precipitacion.assign(**overrides)


def test_validate_data_accepts_valid_precipitacion(tmp_path, messages):
    make_precipitacion().to_csv(tmp_path / "precipitacion_hermosillo.csv", index=False)

    job.validate_data(make_params(tmp_path, "precipitacion_hermosillo"))

    assert "precipitacion_hermosillo: 2 rows pass the quality rules" in "".join(messages)


def test_validate_data_rejects_a_repeated_day(tmp_path, messages):
    broken = make_precipitacion(date=["2024-08-15", "2024-08-15"])
    broken.to_csv(tmp_path / "precipitacion_hermosillo.csv", index=False)

    with pytest.raises(ValueError, match="precipitacion_hermosillo"):
        job.validate_data(make_params(tmp_path, "precipitacion_hermosillo"))

    assert "date failed field_uniqueness" in "".join(messages)


def test_validate_data_rejects_a_rain_day_below_1mm(tmp_path, messages):
    broken = make_precipitacion(is_rain_day=[True, True])
    broken.to_csv(tmp_path / "precipitacion_hermosillo.csv", index=False)

    with pytest.raises(ValueError, match="precipitacion_hermosillo"):
        job.validate_data(make_params(tmp_path, "precipitacion_hermosillo"))

    assert "is_rain_day_is_1mm_or_more" in "".join(messages)


def make_baches_con_colonia(**overrides) -> pd.DataFrame:
    """Un bache dentro de una colonia y otro en carretera, sin colonia."""
    baches = pd.DataFrame(
        {
            "id": [10, 11],
            "date": ["2024-08-15", "2024-08-16"],
            "colonia_id": ["2603000010001", "0"],
            "colonia_source": ["spatial_within", "contexto_ubicacion"],
            "contexto_ubicacion": ["dentro_asentamiento", "probable_carretera_o_zona_rural"],
            "distance_to_colonia_m": [0.0, 1250.0],
        }
    )
    return baches.assign(**overrides)


def test_validate_data_accepts_baches_with_and_without_colonia(tmp_path, messages):
    make_baches_con_colonia().to_csv(tmp_path / "baches_con_colonia.csv", index=False)

    job.validate_data(make_params(tmp_path, "baches_con_colonia"))

    assert "baches_con_colonia: 2 rows pass the quality rules" in "".join(messages)


def test_validate_data_rejects_a_bache_with_colonia_but_no_source(tmp_path, messages):
    broken = make_baches_con_colonia(colonia_id=["2603000010001", "2603000010002"])
    broken.to_csv(tmp_path / "baches_con_colonia.csv", index=False)

    with pytest.raises(ValueError, match="baches_con_colonia"):
        job.validate_data(make_params(tmp_path, "baches_con_colonia"))

    assert "colonia_id_zero_only_without_colonia" in "".join(messages)


def make_contexto(**overrides) -> pd.DataFrame:
    contexto = pd.DataFrame(
        {
            "colonia_id": ["2603000010001", "2603000010002"],
            "id_seg_1": [101, 102],
            "dist_seg_1": [120.0, 800.0],
            "id_seg_2": [103, 104],
            "dist_seg_2": [300.0, 950.0],
            "id_seg_3": [105, 106],
            "dist_seg_3": [410.0, 1200.0],
            "proximity_level": ["Muy cercano", "Lejano"],
            "order_median": [2.0, 1.0],
            "order_max": [4, 1],
            "level_median": [3.0, 5.0],
            "level_min": [2, 4],
            "proximity_ord": [0.0, 2.0],
            "context": [1, 0],
            "context_name": ["Junto a colectores", "Lejos de la red"],
        }
    )
    return contexto.assign(**overrides)


def test_validate_data_accepts_valid_contexto(tmp_path, messages):
    make_contexto().to_csv(tmp_path / "colonias_contexto_hidrografico.csv", index=False)

    job.validate_data(make_params(tmp_path, "colonias_contexto_hidrografico"))

    assert "colonias_contexto_hidrografico: 2 rows pass the quality rules" in "".join(messages)


def test_validate_data_rejects_a_context_with_the_wrong_name(tmp_path, messages):
    broken = make_contexto(context_name=["Lejos de la red", "Lejos de la red"])
    broken.to_csv(tmp_path / "colonias_contexto_hidrografico.csv", index=False)

    with pytest.raises(ValueError, match="colonias_contexto_hidrografico"):
        job.validate_data(make_params(tmp_path, "colonias_contexto_hidrografico"))

    assert "context_name_matches_context" in "".join(messages)


def test_validate_data_rejects_segments_out_of_distance_order(tmp_path, messages):
    broken = make_contexto(dist_seg_2=[90.0, 950.0])
    broken.to_csv(tmp_path / "colonias_contexto_hidrografico.csv", index=False)

    with pytest.raises(ValueError, match="colonias_contexto_hidrografico"):
        job.validate_data(make_params(tmp_path, "colonias_contexto_hidrografico"))

    assert "segments_sorted_by_distance" in "".join(messages)
