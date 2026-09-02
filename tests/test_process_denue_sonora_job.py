from pathlib import Path
import zipfile

import pandas as pd

from project_name.jobs import process_denue_sonora_job as job

RAW_CSV = (
    "id,nom_estab,codigo_act,nombre_act,per_ocu,municipio,localidad,"
    "latitud,longitud,telefono,correoelec,fecha_alta\n"
    "1,ABARROTES LUPITA,112511,Camaronicultura,31 a 50 personas,Hermosillo,"
    "Hermosillo,29.1,-110.9,6621234567,foo@example.com,2010-07\n"
)


def test_process_denue_sonora_extracts_transforms_and_writes_processed_csv(
    tmp_path, monkeypatch
):
    raw_dir = tmp_path / "raw"
    raw_dir.mkdir(parents=True)
    with zipfile.ZipFile(raw_dir / "denue.zip", "w") as archive:
        archive.writestr("conjunto_de_datos/denue.csv", RAW_CSV)

    params = {
        "logging": {"level": "INFO", "file": str(tmp_path / "job.log")},
        "sources": {
            "inegi": {
                "datasets": {
                    "denue_sonora_2024_05": {
                        "raw": {"directory": str(raw_dir), "filename": "denue.zip"},
                        "interim": {"directory": str(tmp_path / "interim")},
                        "processed": {
                            "directory": str(tmp_path / "processed"),
                            "filename": "denue.csv",
                        },
                    }
                }
            }
        },
        "defaults": {"download": {"on_exists": "skip"}},
    }

    monkeypatch.setattr(job, "load_params", lambda: params)

    job.process_denue_sonora(params)

    processed_file = Path(tmp_path / "processed" / "denue.csv")
    result = pd.read_csv(processed_file)

    assert result.loc[0, "business_name"] == "ABARROTES LUPITA"
    assert result.loc[0, "employee_range_rank"] == 4
    assert "phone" not in result.columns
