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
    from project_name.config import load_params
    from project_name.policies.file import FilePolicy, OnExists

    return FilePolicy, HttpClient, OnExists, Path, load_params


@app.cell
def _(load_params):
    params = load_params()
    print(params)
    return (params,)


@app.cell
def _(params):
    defaults = params["defaults"]["download"]
    dataset = params["sources"]["inegi"]["datasets"]["denue_sonora_2024_05"]
    print(defaults)
    print(dataset)
    return dataset, defaults


@app.cell
def _(dataset, defaults):
    download_config = {
            **defaults,
            **dataset.get("download", {}),
        }
    print(download_config)
    return (download_config,)


@app.cell
def _(FilePolicy, OnExists, download_config):
    policy = FilePolicy(
            on_exists=OnExists(download_config["on_exists"])
        )
    return (policy,)


@app.cell
def _(Path, dataset):
    destination = (
            Path(dataset["output"]["directory"])
            / dataset["output"]["filename"]
        )
    print(destination)
    return (destination,)


@app.cell
def _(HttpClient, dataset, destination, policy):
    client = HttpClient(file_policy=policy)

    client.download(
        url=dataset["url"],
        destination=destination,
    )
    return


if __name__ == "__main__":
    app.run()
