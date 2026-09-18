from pathlib import Path

from project_name.jobs import ingest_mg_streets_job as job
from project_name.policies.file import OnExists


def test_ingest_mg_streets_downloads_every_file_of_the_layer(tmp_path, monkeypatch):
    created_clients = []

    class FakeHttpClient:
        def __init__(self, file_policy):
            self.file_policy = file_policy
            self.calls = []
            created_clients.append(self)

        def download_zip_member(self, url, member, destination):
            self.calls.append((url, member, destination))
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(b"layer")

    members = ["conjunto_de_datos/26e.shp", "conjunto_de_datos/26e.dbf"]
    params = {
        "logging": {"level": "INFO", "file": str(tmp_path / "job.log")},
        "sources": {
            "inegi": {
                "name": "INEGI",
                "datasets": {
                    "mg_2025_sonora": {
                        "name": "Calles MG",
                        "url": "https://example.com/26_sonora.zip",
                        "streets_members": members,
                        "raw": {"directory": str(tmp_path / "raw")},
                    }
                }
            }
        },
        "defaults": {"download": {"on_exists": "skip"}},
    }

    monkeypatch.setattr(job, "HttpClient", FakeHttpClient)

    job.ingest_mg_streets(params)

    assert len(created_clients) == 1
    client = created_clients[0]
    assert client.file_policy.on_exists == OnExists.SKIP
    # Cada archivo de la capa queda plano en el directorio raw, sin la carpeta del ZIP.
    # Se descargan en paralelo, así que el orden de las llamadas no importa.
    assert sorted(client.calls) == sorted(
        ("https://example.com/26_sonora.zip", member, Path(tmp_path / "raw") / Path(member).name)
        for member in members
    )

    source_description = (tmp_path / "raw" / "FUENTE.txt").read_text(encoding="utf-8")
    assert source_description.startswith("Calles MG\n")
    assert all(Path(member).name in source_description for member in members)
