import tarfile

from project_name.jobs import snapshot_external_job as job


def make_external(tmp_path):
    root = tmp_path / "external"
    (root / "facebook" / "ocr").mkdir(parents=True)
    (root / "posts.csv").write_text("id,text\n1,hola\n")
    (root / "facebook" / "ocr" / "ocr.csv").write_text("id,text\n1,texto\n")
    (root / ".gitkeep").write_text("")
    (root / "facebook" / ".DS_Store").write_text("junk")
    return root


def test_write_snapshot_writes_checksums_and_archive(tmp_path):
    root = make_external(tmp_path)
    checksums_file = tmp_path / "external.sha256"

    archive = job.write_snapshot(root, checksums_file, tmp_path / "backups")

    assert set(job.read_checksums(checksums_file)) == {"facebook/ocr/ocr.csv", "posts.csv"}
    with tarfile.open(archive) as tar:
        assert sorted(tar.getnames()) == ["external/facebook/ocr/ocr.csv", "external/posts.csv"]


def test_verify_snapshot_passes_on_identical_data(tmp_path):
    root = make_external(tmp_path)
    checksums_file = tmp_path / "external.sha256"
    job.write_snapshot(root, checksums_file, tmp_path / "backups")

    problems = job.verify_snapshot(root, checksums_file)

    assert problems == {"missing": [], "changed": [], "unexpected": []}


def test_verify_snapshot_reports_missing_changed_and_unexpected(tmp_path):
    root = make_external(tmp_path)
    checksums_file = tmp_path / "external.sha256"
    job.write_snapshot(root, checksums_file, tmp_path / "backups")

    (root / "posts.csv").write_text("id,text\n1,cambiado\n")
    (root / "facebook" / "ocr" / "ocr.csv").unlink()
    (root / "nuevo.csv").write_text("x\n")

    problems = job.verify_snapshot(root, checksums_file)

    assert problems == {
        "missing": ["facebook/ocr/ocr.csv"],
        "changed": ["posts.csv"],
        "unexpected": ["nuevo.csv"],
    }
