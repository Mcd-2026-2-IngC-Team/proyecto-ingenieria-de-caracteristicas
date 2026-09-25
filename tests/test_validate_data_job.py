from pathlib import Path

from loguru import logger
import pandas as pd
import pytest

from project_name.jobs import validate_data_job as job


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
            "colonia_id": ["2603000010001", None],
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


def test_validate_data_skips_datasets_without_rules(tmp_path, messages):
    pd.DataFrame({"id": [1]}).to_csv(tmp_path / "baches.csv", index=False)

    job.validate_data(make_params(tmp_path, "baches"))

    assert "No quality rules for baches, skipped" in "".join(messages)
