from pathlib import Path

from project_name.jobs import ingest_dcah_job as job
from project_name.policies.file import OnExists


def test_ingest_dcah_downloads_only_the_state_member(tmp_path, monkeypatch):
    created_clients = []

    class FakeHttpClient:
        def __init__(self, file_policy):
            self.file_policy = file_policy
            self.calls = []
            created_clients.append(self)

        def download_zip_member(self, url, member, destination):
            self.calls.append((url, member, destination))
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(b"zip")

    params = {
        "logging": {"level": "INFO", "file": str(tmp_path / "job.log")},
        "sources": {
            "inegi": {
                "name": "INEGI",
                "datasets": {
                    "dcah_2025": {
                        "name": "Colonias DCAH",
                        "url": "https://example.com/national.zip",
                        "state_member": "26_sonora.zip",
                        "raw": {
                            "directory": str(tmp_path / "raw"),
                            "filename": "dcah_26_sonora.zip",
                        },
                    }
                }
            }
        },
        "defaults": {"download": {"on_exists": "skip"}},
    }

    monkeypatch.setattr(job, "HttpClient", FakeHttpClient)

    job.ingest_dcah(params)

    assert len(created_clients) == 1
    client = created_clients[0]
    assert client.file_policy.on_exists == OnExists.SKIP
    assert client.calls == [
        (
            "https://example.com/national.zip",
            "26_sonora.zip",
            Path(tmp_path / "raw") / "dcah_26_sonora.zip",
        )
    ]

    source_description = (tmp_path / "raw" / "FUENTE.txt").read_text(encoding="utf-8")
    assert source_description.startswith("Colonias DCAH\n")
    assert "por rango: 26_sonora.zip" in source_description
    assert "dcah_26_sonora.zip" in source_description
