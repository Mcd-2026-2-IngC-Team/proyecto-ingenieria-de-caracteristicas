import pandas as pd

from project_name.metadata.dictionary import read_processed_csv


def test_read_processed_csv_keeps_codes_as_text_with_their_zeros(tmp_path):
    csv_file = tmp_path / "colonias_hermosillo.csv"
    pd.DataFrame(
        {"colonia_id": ["2603000010001"], "locality_code": ["0001"], "postal_code": ["00000"]}
    ).to_csv(csv_file, index=False)

    colonias = read_processed_csv(csv_file, "colonias_hermosillo")

    assert colonias.loc[0, ["colonia_id", "locality_code", "postal_code"]].tolist() == [
        "2603000010001",
        "0001",
        "00000",
    ]


def test_read_processed_csv_reads_missing_text_as_empty(tmp_path):
    csv_file = tmp_path / "publicaciones_aguah.csv"
    pd.DataFrame(
        {
            "published_at": ["2024-08-15 12:30:00"],
            "announced_start_at": [None],
            "text": [None],
            "ocr_text": [None],
            "top_comment_text": [None],
        }
    ).to_csv(csv_file, index=False)

    publicaciones = read_processed_csv(csv_file, "publicaciones_aguah")

    assert publicaciones.loc[0, ["text", "ocr_text", "top_comment_text"]].tolist() == [""] * 3
    assert pd.isna(publicaciones.loc[0, "announced_start_at"])
