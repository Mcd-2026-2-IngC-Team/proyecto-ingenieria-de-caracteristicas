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
    pd.DataFrame({"id": [1]}).to_csv(tmp_path / "baches.csv", index=False)

    job.validate_data(make_params(tmp_path, "baches"))

    assert "No quality rules for baches, skipped" in "".join(messages)


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
