from pathlib import Path

import pandas as pd

from project_name.jobs import extract_images_job as job
from project_name.policies.file import OnExists


class FakeHttpClient:
    def __init__(self, file_policy):
        self.file_policy = file_policy
        self.calls = []

    def download(self, url, destination):
        self.calls.append((url, destination))
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(b"fake image bytes")


class FailingHttpClient:
    def __init__(self, file_policy):
        self.file_policy = file_policy
        self.calls = []

    def download(self, url, destination):
        self.calls.append((url, destination))
        raise RuntimeError("expired url")


def write_csv(tmp_path: Path, rows: list[dict]) -> Path:
    source = tmp_path / "dataset_facebook-posts-scraper_2026-06-27.csv"
    pd.DataFrame(rows).to_csv(source, index=False, encoding="utf-8-sig")
    return source


def read_manifest(output_dir: Path, column_slug: str) -> pd.DataFrame:
    return pd.read_csv(output_dir / f"manifest_{column_slug}.csv")


def test_extract_images_downloads_each_populated_url(tmp_path, monkeypatch):
    monkeypatch.setattr(job, "HttpClient", FakeHttpClient)

    source = write_csv(
        tmp_path,
        [
            {"postId": "111", "photo": "https://cdn.example.com/a/one.png?stp=x"},
            {"postId": "222", "photo": "https://cdn.example.com/b/two.jpg"},
        ],
    )
    dest = tmp_path / "images"

    counts = job.extract_images(source=source, dest=dest, column="photo", id_column="postId")

    output_dir = dest / source.stem
    assert counts["downloaded"] == 2
    assert (output_dir / "111_photo.png").exists()
    assert (output_dir / "222_photo.jpg").exists()

    manifest = read_manifest(output_dir, "photo")
    assert set(manifest["status"]) == {"downloaded"}


def test_extract_images_skips_empty_cells(tmp_path, monkeypatch):
    monkeypatch.setattr(job, "HttpClient", FakeHttpClient)

    source = write_csv(
        tmp_path,
        [
            {"postId": "111", "photo": "https://cdn.example.com/a/one.png"},
            {"postId": "222", "photo": ""},
            {"postId": "333", "photo": None},
        ],
    )
    dest = tmp_path / "images"

    counts = job.extract_images(source=source, dest=dest, column="photo", id_column="postId")

    assert counts["downloaded"] == 1
    assert counts["skipped_empty"] == 2


def test_extract_images_skips_missing_id(tmp_path, monkeypatch):
    monkeypatch.setattr(job, "HttpClient", FakeHttpClient)

    source = write_csv(
        tmp_path,
        [
            {"postId": "", "photo": "https://cdn.example.com/a/one.png"},
            {"postId": "222", "photo": "https://cdn.example.com/b/two.png"},
        ],
    )
    dest = tmp_path / "images"

    counts = job.extract_images(source=source, dest=dest, column="photo", id_column="postId")

    assert counts["downloaded"] == 1
    assert counts["skipped_missing_id"] == 1


def test_extract_images_continues_after_download_failure(tmp_path, monkeypatch):
    monkeypatch.setattr(job, "HttpClient", FailingHttpClient)

    source = write_csv(
        tmp_path,
        [
            {"postId": "111", "photo": "https://cdn.example.com/a/one.png"},
            {"postId": "222", "photo": "https://cdn.example.com/b/two.png"},
        ],
    )
    dest = tmp_path / "images"

    counts = job.extract_images(source=source, dest=dest, column="photo", id_column="postId")

    assert counts["failed"] == 2
    assert counts["downloaded"] == 0

    output_dir = dest / source.stem
    manifest = read_manifest(output_dir, "photo")
    assert set(manifest["status"]) == {"failed"}


def test_extract_images_skips_existing_file(tmp_path, monkeypatch):
    monkeypatch.setattr(job, "HttpClient", FakeHttpClient)

    source = write_csv(
        tmp_path,
        [{"postId": "111", "photo": "https://cdn.example.com/a/one.png"}],
    )
    dest = tmp_path / "images"
    output_dir = dest / source.stem
    output_dir.mkdir(parents=True)
    existing = output_dir / "111_photo.png"
    existing.write_bytes(b"already here")

    counts = job.extract_images(
        source=source,
        dest=dest,
        column="photo",
        id_column="postId",
        on_exists=OnExists.SKIP,
    )

    assert counts["skipped_existing"] == 1
    assert counts["downloaded"] == 0
    assert existing.read_bytes() == b"already here"


def test_extract_images_raises_on_unknown_column(tmp_path):
    source = write_csv(
        tmp_path,
        [{"postId": "111", "photo": "https://cdn.example.com/a/one.png"}],
    )
    dest = tmp_path / "images"

    try:
        job.extract_images(source=source, dest=dest, column="imageUrl", id_column="postId")
        raise AssertionError("expected ValueError")
    except ValueError as error:
        assert "imageUrl" in str(error)


def test_extract_images_namespaces_by_source_csv(tmp_path, monkeypatch):
    monkeypatch.setattr(job, "HttpClient", FakeHttpClient)

    source_a = write_csv(
        tmp_path,
        [{"postId": "111", "photo": "https://cdn.example.com/a/one.png"}],
    )
    source_b = tmp_path / "dataset_facebook-posts-scraper_2026-07-04.csv"
    pd.DataFrame([{"postId": "111", "photo": "https://cdn.example.com/a/one.png"}]).to_csv(
        source_b, index=False, encoding="utf-8-sig"
    )

    dest = tmp_path / "images"

    job.extract_images(source=source_a, dest=dest, column="photo", id_column="postId")
    job.extract_images(source=source_b, dest=dest, column="photo", id_column="postId")

    assert (dest / source_a.stem / "111_photo.png").exists()
    assert (dest / source_b.stem / "111_photo.png").exists()
