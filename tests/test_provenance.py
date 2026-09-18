from datetime import UTC, datetime
import hashlib
import os

from project_name.provenance import SOURCE_DESCRIPTION_FILENAME, write_source_description

SOURCE = {
    "name": "Instituto Nacional de Estadística y Geografía",
    "url": "https://www.inegi.org.mx",
    "license": "Términos de Libre Uso de la Información del INEGI",
}


def make_dataset(raw_dir, **extra):
    return {
        "name": "Delimitación de colonias 2025",
        "url": "https://example.com/national.zip",
        "raw": {"directory": str(raw_dir)},
        **extra,
    }


def test_write_source_description_documents_source_and_files(tmp_path):
    raw_dir = tmp_path / "raw"
    raw_dir.mkdir()
    data_file = raw_dir / "sonora.zip"
    data_file.write_bytes(b"zip bytes")
    downloaded_at = datetime(2026, 9, 18, 13, 2, tzinfo=UTC).timestamp()
    os.utime(data_file, (downloaded_at, downloaded_at))
    dataset = make_dataset(
        raw_dir,
        description="Polígonos de colonias\n  entregados por cada municipio.",
        documentation=["https://www.inegi.org.mx/programas/dcah/"],
    )

    written = write_source_description(
        SOURCE, dataset, files=[data_file], job="ingest_dcah_job", members=["26_sonora.zip"]
    )

    text = written.read_text(encoding="utf-8")
    assert written == raw_dir / SOURCE_DESCRIPTION_FILENAME
    assert text.startswith("Delimitación de colonias 2025\n")
    assert "Fuente: Instituto Nacional de Estadística y Geografía (https://www.inegi.org.mx)" in text
    assert "https://example.com/national.zip" in text
    assert "por rango: 26_sonora.zip" in text
    # La descripción del YAML se reacomoda en una sola línea con sangría.
    assert "  Polígonos de colonias entregados por cada municipio." in text
    assert "  - https://www.inegi.org.mx/programas/dcah/" in text
    assert "Licencia: Términos de Libre Uso de la Información del INEGI" in text
    # La fecha de descarga es la fecha de modificación del archivo, en UTC.
    assert "2026-09-18 13:02" in text
    assert hashlib.sha256(b"zip bytes").hexdigest() in text
    assert "Generado por ingest_dcah_job" in text


def test_write_source_description_omits_optional_sections(tmp_path):
    raw_dir = tmp_path / "raw"
    raw_dir.mkdir()
    data_file = raw_dir / "data.csv"
    data_file.write_text("a,b\n")

    written = write_source_description(
        {"name": "Fuente sin sitio"}, make_dataset(raw_dir), files=[data_file], job="job"
    )

    text = written.read_text(encoding="utf-8")
    assert "Fuente: Fuente sin sitio\n" in text
    assert "Descripción" not in text
    assert "Documentación" not in text
    assert "Licencia" not in text
    assert "por rango" not in text
    assert "data.csv" in text
