"""Valida el CSV enriquecido y exporta nueve columnas, sin eliminar registros.

Desde la raíz del proyecto:
    uv run python path/to/data_quality_baches.py
    uv run python path/to/data_quality_baches.py --input entrada.csv --output salida.csv

Requiere pandas. Las rutas relativas se resuelven desde el directorio actual.
Los errores impiden escribir la salida; las discrepancias espaciales se informan.
No infiere colonias ni reconstruye fechas faltantes.
"""
from __future__ import annotations

import argparse
import os
from pathlib import Path
import tempfile

import pandas as pd

FINAL_COLUMNS = [
    "id", "latitude", "longitude", "date", "date_mx", "year",
    "material", "description", "colonia",
]


def validate_and_select(df: pd.DataFrame) -> pd.DataFrame:
    """Valida datos obligatorios y devuelve las columnas finales en orden."""
    missing = sorted(set(FINAL_COLUMNS) - set(df.columns))
    if missing:
        raise ValueError(f"Faltan columnas obligatorias: {missing}")
    if df.empty:
        raise ValueError("El dataset está vacío.")

    errors = []

    def check(name: str, invalid: pd.Series) -> None:
        mask = invalid.fillna(True)
        count = int(mask.sum())
        print(f"{name}: {count} registros con problema")
        if count:
            sample = df.loc[mask, "id"].head(10).tolist()
            errors.append(f"{name}: {count}; ejemplos de id: {sample}")

    # Nulos y blancos en las columnas finales.
    for column in FINAL_COLUMNS:
        blank = df[column].astype("string").str.strip().eq("").fillna(False)
        check(f"{column} faltante", df[column].isna() | blank)

    check("id duplicado", df["id"].duplicated(keep=False))
    print(f"Filas completas duplicadas: {int(df.duplicated().sum())}")

    latitude = pd.to_numeric(df["latitude"], errors="coerce")
    longitude = pd.to_numeric(df["longitude"], errors="coerce")
    check("latitude inválida", ~latitude.between(-90, 90))
    check("longitude inválida", ~longitude.between(-180, 180))

    date = pd.to_datetime(df["date"], format="%Y-%m-%d", errors="coerce")
    date_mx = pd.to_datetime(df["date_mx"], format="%d/%m/%Y", errors="coerce")
    year = pd.to_numeric(df["year"], errors="coerce")
    check("date inválida", date.isna())
    check("date_mx inválida", date_mx.isna())
    check("date y date_mx inconsistentes", date.notna() & date_mx.notna() & date.ne(date_mx))
    year_from_date = date.dt.year

    year_mismatch = date.notna() & (
        year.isna() | year.ne(year_from_date)
    )

    print(
        f"Años actualizados a partir de date: {int(year_mismatch.sum())}"
    )

    year = year.where(~year_mismatch, year_from_date)

    # Auditoría disponible antes de retirar las columnas auxiliares.
    if "distance_to_colonia_m" in df.columns:
        distance = pd.to_numeric(df["distance_to_colonia_m"], errors="coerce")
        check("distance_to_colonia_m inválida", distance.isna() | distance.lt(0) | distance.eq(float("inf")))
        print("Distancia a colonia (m):")
        print(distance.describe(percentiles=[.5, .75, .9, .95, .99]).to_string())
    for column in ["material", "colonia_source", "spatial_match_method",
                   "contexto_ubicacion", "fuera_asentamiento", "settlement_type"]:
        if column in df.columns:
            print(f"\nDistribución de {column}:")
            print(df[column].value_counts(dropna=False).to_string())
    if "colonia_match" in df.columns:
        matches = df["colonia_match"].astype("string").str.strip().str.lower()
        comparable = matches.isin(["true", "false"])
        mismatches = int(matches.eq("false").sum())
        total = int(comparable.sum())
        print(f"\nDiscrepancias de colonia: {mismatches}/{total} comparables")
        if total:
            print(f"Porcentaje de discrepancias: {100 * mismatches / total:.2f}%")
    context = df["colonia"].isin(["cerca_asentamiento", "probable_carretera_o_zona_rural"])
    print(f"Colonias con etiqueta de contexto (se conservan): {int(context.sum())}")

    if errors:
        raise ValueError("Validación fallida. No se exportó el CSV:\n- " + "\n- ".join(errors))

    result = df.loc[:, FINAL_COLUMNS].copy()
    result["latitude"] = latitude
    result["longitude"] = longitude
    result["date"] = date.dt.strftime("%Y-%m-%d")
    result["date_mx"] = date_mx.dt.strftime("%d/%m/%Y")
    result["year"] = year.astype("int64")
    return result


def run(input_path: Path, output_path: Path) -> None:
    if input_path.resolve() == output_path.resolve():
        raise ValueError("Entrada y salida deben ser archivos distintos.")
    # Conserva identificadores y códigos como texto, incluidos ceros iniciales.
    df = pd.read_csv(input_path, encoding="utf-8-sig", dtype="string")
    print(f"Entrada: {input_path.resolve()}\nRegistros: {len(df)}")
    result = validate_and_select(df)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    # Escritura atómica: evita dejar un CSV parcial ante un error.
    fd, name = tempfile.mkstemp(dir=output_path.parent, suffix=".csv")
    os.close(fd)
    temporary = Path(name)
    try:
        result.to_csv(temporary, index=False, encoding="utf-8")
        os.replace(temporary, output_path)
    finally:
        temporary.unlink(missing_ok=True)
    print(f"\nGuardado: {output_path.resolve()}\nShape: {result.shape}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--input", type=Path, default=Path("data/processed/bachometro/baches_hermosillo_filled.csv"))
    parser.add_argument("--output", type=Path, default=Path("data/processed/bachometro/baches_hermosillo_clean.csv"))
    args = parser.parse_args()
    try:
        run(args.input, args.output)
    except (ValueError, OSError, pd.errors.ParserError) as error:
        parser.exit(1, f"ERROR: {error}\n")


if __name__ == "__main__":
    main()
