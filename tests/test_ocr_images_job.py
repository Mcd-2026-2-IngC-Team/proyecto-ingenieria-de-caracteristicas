import json

import pandas as pd

from project_name.jobs import ocr_images_job as job


class FakeOcrClient:
    def __init__(self, device="auto"):
        self.device = device
        self.calls = []

    def extract_text(self, image_path):
        self.calls.append(image_path)
        if image_path.name == "bad.jpg":
            raise RuntimeError("corrupt image")
        return f"text from {image_path.name}"


def write_manifest(tmp_path, rows: list[dict]):
    output_dir = tmp_path / "images" / "dataset_facebook-posts-scraper_2025-01-01-to-2025-06-02"
    output_dir.mkdir(parents=True)
    manifest = output_dir / "manifest_media-0-photo_image-uri.csv"
    pd.DataFrame(rows).to_csv(manifest, index=False)

    for row in rows:
        if row["status"] == "downloaded":
            (output_dir / row["filename"]).write_bytes(b"fake bytes")

    return manifest


def ocr_output(tmp_path, manifest):
    return tmp_path / "ocr" / manifest.parent.name / "ocr_media-0-photo_image-uri.csv"


def test_ocr_images_runs_only_downloaded_rows(tmp_path, monkeypatch):
    monkeypatch.setattr(job, "OcrClient", FakeOcrClient)

    manifest = write_manifest(
        tmp_path,
        [
            {"id": "111", "filename": "111_photo.jpg", "status": "downloaded"},
            {"id": "222", "filename": None, "status": "skipped_empty"},
        ],
    )

    counts = job.ocr_images(manifest=manifest, output_dir=tmp_path / "ocr")

    assert counts == {"ocr_success": 1, "ocr_failed": 0, "skipped_no_image": 1}

    output = pd.read_csv(ocr_output(tmp_path, manifest))
    assert output.loc[output["id"] == 111, "status"].item() == "ocr_success"
    assert output.loc[output["id"] == 111, "text"].item() == "text from 111_photo.jpg"
    assert output.loc[output["id"] == 222, "status"].item() == "skipped_no_image"


def test_ocr_images_continues_after_failure(tmp_path, monkeypatch):
    monkeypatch.setattr(job, "OcrClient", FakeOcrClient)

    manifest = write_manifest(
        tmp_path,
        [
            {"id": "111", "filename": "bad.jpg", "status": "downloaded"},
            {"id": "222", "filename": "222_photo.jpg", "status": "downloaded"},
        ],
    )

    counts = job.ocr_images(manifest=manifest, output_dir=tmp_path / "ocr")

    assert counts == {"ocr_success": 1, "ocr_failed": 1, "skipped_no_image": 0}

    output = pd.read_csv(ocr_output(tmp_path, manifest))
    assert output.loc[output["id"] == 111, "status"].item() == "ocr_failed"
    assert output.loc[output["id"] == 222, "status"].item() == "ocr_success"


def test_ocr_images_writes_output_outside_images_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(job, "OcrClient", FakeOcrClient)

    manifest = write_manifest(
        tmp_path,
        [{"id": "111", "filename": "111_photo.jpg", "status": "downloaded"}],
    )

    job.ocr_images(manifest=manifest, output_dir=tmp_path / "ocr")

    assert ocr_output(tmp_path, manifest).exists()
    assert not (manifest.parent / "ocr_media-0-photo_image-uri.csv").exists()


def test_ocr_images_writes_provenance_next_to_output(tmp_path, monkeypatch):
    monkeypatch.setattr(job, "OcrClient", FakeOcrClient)
    monkeypatch.setenv("SLURM_JOB_ID", "123")

    manifest = write_manifest(
        tmp_path,
        [{"id": "111", "filename": "111_photo.jpg", "status": "downloaded"}],
    )

    job.ocr_images(manifest=manifest, output_dir=tmp_path / "ocr", device="gpu:0")

    meta_path = ocr_output(tmp_path, manifest).with_suffix(".meta.json")
    meta = json.loads(meta_path.read_text())
    assert meta["counts"] == {"ocr_success": 1, "ocr_failed": 0, "skipped_no_image": 0}
    assert meta["device"] == "gpu:0"
    assert meta["slurm_job_id"] == "123"
    assert set(meta["packages"]) == set(job.PROVENANCE_PACKAGES)


def test_ocr_image_returns_extracted_text(tmp_path, monkeypatch):
    monkeypatch.setattr(job, "OcrClient", FakeOcrClient)

    image = tmp_path / "one.jpg"
    image.write_bytes(b"fake bytes")

    text = job.ocr_image(image=image)

    assert text == "text from one.jpg"
