from pathlib import Path

from project_name.jobs import ingest_denue_sonora_job as job
from project_name.policies.file import OnExists


def test_ingest_denue_sonora_downloads_to_raw_directory(tmp_path, monkeypatch):
    """Regression test: the job must use dataset["raw"], not a stale dataset["output"]."""
    created_clients = []

    class FakeHttpClient:
        def __init__(self, file_policy):
            self.file_policy = file_policy
            self.calls = []
            created_clients.append(self)

        def download(self, url, destination):
            self.calls.append((url, destination))

    params = {
        "logging": {"level": "INFO", "file": str(tmp_path / "job.log")},
        "sources": {
            "inegi": {
                "datasets": {
                    "denue_sonora_2024_05": {
                        "url": "https://example.com/denue.zip",
                        "raw": {
                            "directory": str(tmp_path / "raw"),
                            "filename": "denue.zip",
                        },
                    }
                }
            }
        },
        "defaults": {"download": {"on_exists": "skip"}},
    }

    monkeypatch.setattr(job, "load_params", lambda: params)
    monkeypatch.setattr(job, "HttpClient", FakeHttpClient)

    job.ingest_denue_sonora(params)

    assert len(created_clients) == 1
    client = created_clients[0]
    assert client.file_policy.on_exists == OnExists.SKIP
    assert client.calls == [
        ("https://example.com/denue.zip", Path(tmp_path / "raw") / "denue.zip")
    ]
