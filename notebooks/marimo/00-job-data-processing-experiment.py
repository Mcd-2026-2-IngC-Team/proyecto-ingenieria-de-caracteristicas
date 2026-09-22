import marimo

__generated_with = "0.24.0"
app = marimo.App()


@app.cell
def _():
    import marimo as mo

    return (mo,)


@app.cell
def _():
    from pathlib import Path
    import zipfile

    import matplotlib.pyplot as plt
    import pandas as pd

    from project_name.clients.http import HttpClient
    from project_name.config import (
        load_dataset_config,
        load_logging,
        load_params,
    )
    from project_name.logging import log_execution
    from project_name.policies.file import FilePolicy, OnExists

    return Path, load_dataset_config, load_params, pd, plt, zipfile


@app.cell
def _(load_params):
    params = load_params()
    print(params)
    return (params,)


@app.cell
def _(Path, load_dataset_config, params):
    dataset = load_dataset_config(
        params,
        source="inegi",
        dataset="denue_sonora_2024_05",
    )

    raw_file = Path(dataset["raw"]["directory"]) / dataset["raw"]["filename"]

    interim_dir = Path(dataset["interim"]["directory"])
    return dataset, interim_dir, raw_file


@app.cell
def _(raw_file):
    assert raw_file.exists()
    return


@app.cell
def _(interim_dir, raw_file, zipfile):
    interim_dir.mkdir(parents=True, exist_ok=True)

    with zipfile.ZipFile(raw_file, "r") as archive:
        archive.extractall(interim_dir)

    for file in interim_dir.iterdir():
        print(file)
    return


@app.cell
def _(interim_dir, pd):
    csv_file = next((interim_dir / "conjunto_de_datos").glob("*.csv"))

    # El INEGI publica estos archivos en ISO-8859-1, no UTF-8; utf-8 lanza UnicodeDecodeError.
    # low_memory=False evita un DtypeWarning al inferir el tipo de columnas mixtas (ej. telefono).
    df = pd.read_csv(csv_file, encoding="latin-1", low_memory=False)

    print(df.shape)
    print(df.columns.tolist())
    df.head()
    return (df,)


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## De interim a processed
    Seleccionamos las columnas relevantes del directorio DENUE, aplicamos algunas
    transformaciones de ejemplo (feature engineering) y guardamos el resultado como
    CSV en `data/processed/`.
    """)
    return


@app.cell
def _(Path, dataset):
    processed_dir = Path(dataset["processed"]["directory"])

    # params.yml declara un archivo .parquet; por ahora exploramos guardando CSV.
    processed_file = processed_dir / Path(
        dataset["processed"]["filename"]
    ).with_suffix(".csv")
    return processed_dir, processed_file


@app.cell
def _(df):
    # Nos quedamos solo con las columnas relevantes para esta exploración.
    columns = {
        "id": "id",
        "nom_estab": "business_name",
        "codigo_act": "activity_code",
        "nombre_act": "activity_name",
        "per_ocu": "employee_range",
        "municipio": "municipality",
        "localidad": "locality",
        "latitud": "latitude",
        "longitud": "longitude",
        "telefono": "phone",
        "correoelec": "email",
        "fecha_alta": "registration_date",
    }

    denue = df[list(columns)].rename(columns=columns)
    denue.head()
    return (denue,)


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ### Transformaciones de ejemplo
    - `employee_range` → `employee_range_rank`: codificamos el rango de personal
      ocupado como un valor ordinal, ya que pandas no puede inferir su orden natural.
    - `registration_date`: se convierte a un `datetime` real a partir del string `YYYY-MM`.
    - `phone` / `email`: como la mayoría de los registros no los tienen, los
      reemplazamos por banderas booleanas (`has_phone`, `has_email`) que indican
      presencia en vez de guardar el valor crudo.
    """)
    return


@app.cell
def _(denue, pd):
    # Los rangos tienen un orden natural que pandas no puede inferir solo.
    employee_range_order = {
        "0 a 5 personas": 1,
        "6 a 10 personas": 2,
        "11 a 30 personas": 3,
        "31 a 50 personas": 4,
        "51 a 100 personas": 5,
        "101 a 250 personas": 6,
        "251 y más personas": 7,
    }

    # Un par de valores usan espacio en vez de guion (ej. "2013 07"); los normalizamos.
    registration_date = denue["registration_date"].str.replace(
        " ", "-", regex=False
    )

    denue_clean = denue.assign(
        employee_range_rank=denue["employee_range"].map(employee_range_order),
        registration_date=pd.to_datetime(registration_date, format="%Y-%m"),
        # La mayoría de los registros no tienen teléfono/correo; la presencia
        # es una señal más útil que el valor crudo.
        has_phone=denue["phone"].notna(),
        has_email=denue["email"].notna(),
    ).drop(columns=["phone", "email"])

    denue_clean.dtypes
    return (denue_clean,)


@app.cell
def _(denue_clean):
    denue_clean.head()
    return


@app.cell
def _(denue_clean, processed_dir, processed_file):
    processed_dir.mkdir(parents=True, exist_ok=True)
    denue_clean.to_csv(processed_file, index=False)

    print(f"Guardadas {len(denue_clean)} filas -> {processed_file}")
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## Visualizaciones
    Leemos el CSV recién guardado en `data/processed/` (no el dataframe en memoria)
    para confirmar que lo que quedó en disco es justo lo que queremos graficar.
    """)
    return


@app.cell
def _(pd, processed_file):
    processed_df = pd.read_csv(processed_file, parse_dates=["registration_date"])
    processed_df.head()
    return (processed_df,)


@app.cell
def _(plt, processed_df):
    # Top 10 actividades económicas por número de establecimientos.
    top_activities = processed_df["activity_name"].value_counts().head(10).sort_values()

    fig_activities, ax_activities = plt.subplots(figsize=(8, 5))
    top_activities.plot.barh(ax=ax_activities)
    ax_activities.set_xlabel("Número de establecimientos")
    ax_activities.set_title("Top 10 actividades económicas")
    fig_activities
    return


@app.cell
def _(plt, processed_df):
    # Distribución de establecimientos por rango de personal ocupado,
    # ordenada por employee_range_rank en vez del orden alfabético.
    employee_range_counts = processed_df.groupby(
        ["employee_range_rank", "employee_range"]
    ).size()

    fig_employee_range, ax_employee_range = plt.subplots(figsize=(8, 5))
    employee_range_counts.reset_index(level=0, drop=True).plot.bar(ax=ax_employee_range)
    ax_employee_range.set_ylabel("Número de establecimientos")
    ax_employee_range.set_title("Distribución por rango de personal ocupado")
    ax_employee_range.tick_params(axis="x", rotation=45)
    fig_employee_range
    return


@app.cell
def _(plt, processed_df):
    # Distribución geográfica: cada establecimiento como un punto lat/long.
    fig_map, ax_map = plt.subplots(figsize=(6, 6))
    ax_map.scatter(processed_df["longitude"], processed_df["latitude"], s=2, alpha=0.3)
    ax_map.set_xlabel("Longitud")
    ax_map.set_ylabel("Latitud")
    ax_map.set_title("Distribución geográfica de establecimientos")
    fig_map
    return


if __name__ == "__main__":
    app.run()
