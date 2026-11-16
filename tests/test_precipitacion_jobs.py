import json
from urllib.parse import parse_qs, urlparse

from project_name.jobs import ingest_precipitacion_job as ingest
from project_name.jobs import process_precipitacion_job as process


def make_params(tmp_path) -> dict:
    return {
        "logging": {"level": "INFO", "file": str(tmp_path / "job.log")},
        "sources": {
            "open_meteo": {
                "name": "Open-Meteo",
                "license": "CC-BY-4.0",
                "datasets": {
                    "precipitacion_hermosillo": {
                        "name": "Precipitación diaria",
                        "url": "https://example.com/v1/archive",
                        "query": {
                            "latitude": 29.0892,
                            "longitude": -110.9613,
                            "start_date": "2024-07-01",
                            "end_date": "2024-07-03",
                            "daily": "precipitation_sum,precipitation_hours",
                            "timezone": "America/Hermosillo",
                        },
                        "raw": {"directory": str(tmp_path / "raw"), "filename": "lluvia.json"},
                        "processed": {
                            "directory": str(tmp_path / "processed"),
                            "filename": "lluvia.csv",
                        },
                    }
                },
            }
        },
        "defaults": {"download": {"on_exists": "skip"}},
    }


def make_payload() -> dict:
    return {
        "daily": {
            "time": ["2024-07-01", "2024-07-02", "2024-07-03"],
            "precipitation_sum": [0.0, 0.4, 23.5],
            "precipitation_hours": [0.0, 1.0, 5.0],
        }
    }


def test_build_archive_url_keeps_every_query_parameter(tmp_path):
    dataset = make_params(tmp_path)["sources"]["open_meteo"]["datasets"][
        "precipitacion_hermosillo"
    ]

    url = urlparse(ingest.build_archive_url(dataset))
    query = parse_qs(url.query)

    assert url.netloc == "example.com"
    assert query["start_date"] == ["2024-07-01"]
    assert query["daily"] == ["precipitation_sum,precipitation_hours"]
    assert query["timezone"] == ["America/Hermosillo"]


def test_ingest_downloads_the_archive_and_writes_its_source(tmp_path, monkeypatch):
    calls = []

    class FakeHttpClient:
        def __init__(self, file_policy):
            self.file_policy = file_policy

        def download(self, url, destination):
            calls.append(url)
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_text(json.dumps(make_payload()), encoding="utf-8")

    monkeypatch.setattr(ingest, "HttpClient", FakeHttpClient)

    ingest.ingest_precipitacion(make_params(tmp_path))

    assert len(calls) == 1 and calls[0].startswith("https://example.com/v1/archive?")
    source = (tmp_path / "raw" / "FUENTE.txt").read_text(encoding="utf-8")
    assert source.startswith("Precipitación diaria\n")
    assert "CC-BY-4.0" in source


def test_build_precipitacion_marks_rain_days_from_one_millimetre():
    frame = process.build_precipitacion(make_payload())

    assert list(frame.columns) == [
        "date",
        "precipitation_mm",
        "precipitation_hours",
        "year",
        "month",
        "is_rain_day",
    ]
    # La llovizna de 0.4 mm no cuenta como día de lluvia.
    assert frame["is_rain_day"].tolist() == [False, False, True]
    assert frame["month"].unique().tolist() == [7]


def test_process_writes_one_row_per_day(tmp_path):
    params = make_params(tmp_path)
    raw = tmp_path / "raw" / "lluvia.json"
    raw.parent.mkdir(parents=True)
    raw.write_text(json.dumps(make_payload()), encoding="utf-8")

    process.process_precipitacion(params)

    written = (tmp_path / "processed" / "lluvia.csv").read_text(encoding="utf-8").splitlines()
    assert len(written) == 1 + 3
