import marimo

__generated_with = "0.24.0"
app = marimo.App(width="medium")


@app.cell
def _():
    import marimo as mo

    return (mo,)


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    # Objectivos del experimento
    1. Descargar datos de una fuente de datos.
    2. Genere un archivo texto con la descripción de las fuentes, las fechas de descarga y de ser posible la descripción (o enlaces) que expliquen la naturaleza de los datos descargados. Si los datos venían sin explicación, agregar la explicación propia para simplificar el proceso. Los datos se deberán guardar en `.data/raw/`.
    3. Logging
    """)
    return


@app.cell
def _():
    from pathlib import Path

    from project_name.clients.http import HttpClient
    from project_name.clients.inegi import InegiClient
    from project_name.config import load_params, load_dataset_config
    from project_name.policies.file import FilePolicy, OnExists

    return (
        FilePolicy,
        HttpClient,
        OnExists,
        Path,
        load_dataset_config,
        load_params,
    )


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

    raw_file = (
        Path(dataset["raw"]["directory"])
        / dataset["raw"]["filename"]
    )
    return dataset, raw_file


@app.cell
def _(FilePolicy, HttpClient, OnExists, dataset, raw_file):
    policy = FilePolicy(on_exists=OnExists(dataset["download"]["on_exists"]))

    client = HttpClient(file_policy=policy)
    client.download(
        url=dataset["url"],
        destination=raw_file,
    )
    return


if __name__ == "__main__":
    app.run()
