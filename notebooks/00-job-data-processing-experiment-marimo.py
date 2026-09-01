import marimo

__generated_with = "0.24.0"
app = marimo.App()


@app.cell
def _():
    from pathlib import Path
    import zipfile

    from project_name.clients.http import HttpClient
    from project_name.config import load_dataset_config, load_logging, load_params
    from project_name.logging import log_execution
    from project_name.policies.file import FilePolicy, OnExists

    return Path, load_dataset_config, load_params, zipfile


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

    interim_dir = Path(dataset["interim"]["directory"])
    return interim_dir, raw_file


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
def _():
    return


if __name__ == "__main__":
    app.run()
