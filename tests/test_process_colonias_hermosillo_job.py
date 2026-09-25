from pathlib import Path
import zipfile

import geopandas as gpd
import pandas as pd
import pytest
from shapely.geometry import Polygon

from project_name.geocoding import LAMBERT_MEXICO
from project_name.jobs import process_colonias_hermosillo_job as job


def make_params(tmp_path: Path) -> dict:
    return {
        "defaults": {"download": {"on_exists": "skip"}},
        "sources": {
            "inegi": {
                "datasets": {
                    "dcah_2025": {
                        "raw": {"directory": str(tmp_path / "raw"), "filename": "dcah.zip"},
                        "interim": {"directory": str(tmp_path / "interim")},
                    }
                }
            },
            "agua_hermosillo": {
                "datasets": {
                    "colonias_hermosillo": {
                        "processed": {
                            "directory": str(tmp_path / "processed"),
                            "filename": "colonias.csv",
                        }
                    }
                }
            },
        },
    }


def write_dcah_zip(tmp_path: Path) -> None:
    """Un ZIP con la misma estructura que el del INEGI: la capa 26as en conjunto_de_datos/."""
    settlements = gpd.GeoDataFrame(
        {
            "cve_mun": ["030"],
            "cvegeo": ["2603000010001"],
            "nom_asen": ["Centro"],
            "tipo": ["COLONIA"],
            "cve_loc": ["0001"],
            "cp": ["83000"],
            "fecha_act": ["11/2025"],
            "geometry": [Polygon([(0, 0), (100, 0), (100, 100), (0, 100)])],
        },
        crs=LAMBERT_MEXICO,
    )
    layer_dir = tmp_path / "layer"
    layer_dir.mkdir()
    settlements.to_file(layer_dir / "26as.shp")

    raw_dir = tmp_path / "raw"
    raw_dir.mkdir()
    with zipfile.ZipFile(raw_dir / "dcah.zip", "w") as archive:
        for part in layer_dir.iterdir():
            archive.write(part, f"conjunto_de_datos/{part.name}")


def test_process_colonias_hermosillo_extracts_the_raw_zip_before_reading_it(tmp_path):
    write_dcah_zip(tmp_path)

    job.process_colonias_hermosillo(make_params(tmp_path))

    assert (tmp_path / "interim" / "conjunto_de_datos" / "26as.shp").exists()
    colonias = pd.read_csv(tmp_path / "processed" / "colonias.csv", dtype=str)
    assert list(colonias["settlement_name"]) == ["Centro"]
    assert (tmp_path / "processed" / "colonias.gpkg").exists()


def test_process_colonias_hermosillo_asks_for_download_when_raw_zip_is_missing(tmp_path):
    with pytest.raises(FileNotFoundError, match="make download"):
        job.process_colonias_hermosillo(make_params(tmp_path))


def test_safe_extract_rejects_members_outside_the_destination(tmp_path):
    zip_file = tmp_path / "evil.zip"
    with zipfile.ZipFile(zip_file, "w") as archive:
        archive.writestr("../escaped.txt", "x")

    with zipfile.ZipFile(zip_file) as archive, pytest.raises(ValueError, match="Unsafe path"):
        job.safe_extract(archive, tmp_path / "interim")

    assert not (tmp_path / "escaped.txt").exists()
