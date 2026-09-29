# project_name/jobs/clean_neighborhoods_job.py

from pathlib import Path

import pandas as pd

from project_name.config import (
    load_dataset_config,
    load_logging,
    load_params,
)


def clean_neighborhoods(input_file: Path, output_file: Path) -> None:
    """Clean neighborhood data by removing rows without useful information."""

    df = pd.read_csv(input_file)

    # Convert empty strings / whitespace-only strings to NaN
    columns_to_clean = ["material", "calle", "colonia"]

    for column in columns_to_clean:
        df[column] = df[column].replace(r"^\s*$", pd.NA, regex=True)

    # Remove rows where material, calle and colonia are all empty
    df = df.dropna(
        subset=columns_to_clean,
        how="all",
    )

    # Reset index after removing rows
    df = df.reset_index(drop=True)

    output_file.parent.mkdir(parents=True, exist_ok=True)

    df.to_csv(output_file, index=False)

    print(f"Cleaned data saved to: {output_file}")
    print(f"Rows: {len(df)}")


def main() -> None:
    params = load_params()

    dataset = load_dataset_config(
        params,
        source="bachometro",
        dataset="baches",
    )

    processed_directory = Path(
        dataset["processed"]["directory"]
    )

    input_file = (
        processed_directory
        / "relacion_colonia_baches_id.csv"
    )

    output_file = (
        processed_directory
        / "relacion_colonia_baches_id_clean.csv"
    )

    clean_neighborhoods(
        input_file=input_file,
        output_file=output_file,
    )


if __name__ == "__main__":
    main()