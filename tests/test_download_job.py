import pytest

from project_name.jobs import download_job as job


def test_download_runs_every_ingest_job_once(monkeypatch):
    calls = []

    def make_job(name):
        def fake_job(params):
            calls.append((name, params))

        return fake_job

    monkeypatch.setattr(job, "INGEST_JOBS", tuple(make_job(n) for n in ("a", "b", "c")))
    params = {"sources": {}}

    job.download(params)

    # Corren en paralelo, así que no importa el orden: solo que cada una corra una vez.
    assert sorted(name for name, _ in calls) == ["a", "b", "c"]
    assert all(received is params for _, received in calls)


def test_download_propagates_a_failing_source(monkeypatch):
    def failing_job(params):
        raise ConnectionError("INEGI no responde")

    monkeypatch.setattr(job, "INGEST_JOBS", (lambda params: None, failing_job))

    with pytest.raises(ConnectionError, match="INEGI"):
        job.download({})
