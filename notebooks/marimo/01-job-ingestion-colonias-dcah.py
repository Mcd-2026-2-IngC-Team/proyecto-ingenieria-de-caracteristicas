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
    # Ingesta de colonias de Hermosillo (INEGI, DCAH 2025)

    El INEGI publica las colonias como
    información propia en el programa **Delimitación de Colonias y otros Asentamientos
    Humanos (DCAH)**: polígonos por cada municipio.

    ## Objetivos del experimento
    1. Descargar el DCAH 2025 con el cliente del INEGI, usando la fuente declarada en `params.yml`.
       El INEGI solo publica un paquete nacional con un ZIP por estado, así que bajamos
       únicamente el de Sonora.
    2. Extraerlo en `data/interim/`.
    3. Leer la capa de asentamientos y entender su sistema de coordenadas.
    4. Filtrar Hermosillo y explorar qué trae: tipos de asentamiento, nombres, áreas.
    5. Comprobar que las colonias que aparecen en los avisos de Agua de Hermosillo existen en la capa.
    """)
    return


@app.cell
def _():
    from pathlib import Path
    import re
    import unicodedata
    import zipfile

    import geopandas as gpd
    import matplotlib.pyplot as plt
    import pandas as pd

    from project_name.clients.http import HttpClient
    from project_name.clients.inegi import InegiClient
    from project_name.config import load_dataset_config, load_params
    from project_name.policies.file import FilePolicy, OnExists

    return (
        FilePolicy,
        HttpClient,
        InegiClient,
        OnExists,
        Path,
        gpd,
        load_dataset_config,
        load_params,
        pd,
        plt,
        re,
        unicodedata,
        zipfile,
    )


@app.cell
def _(Path, load_dataset_config, load_params):
    params = load_params()
    dataset = load_dataset_config(params, source="inegi", dataset="dcah_2025")

    raw_file = Path(dataset["raw"]["directory"]) / dataset["raw"]["filename"]
    interim_dir = Path(dataset["interim"]["directory"])
    dataset
    return dataset, interim_dir, raw_file


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## Descarga
    El paquete nacional pesa ~556 MB, pero solo necesitamos `26_sonora.zip` (~15 MB).
    `download_zip_member` lee el índice del ZIP remoto (al final del archivo) y pide
    al servidor únicamente los bytes de ese miembro, con peticiones HTTP por rango.
    Una primera prueba bajando el paquete completo se cortó por timeout a los 492 MB.

    La política `on_exists: skip` de `params.yml` omite la descarga si el archivo ya
    está en `data/raw/`.
    """)
    return


@app.cell
def _(FilePolicy, HttpClient, InegiClient, OnExists, dataset, raw_file):
    policy = FilePolicy(on_exists=OnExists(dataset["download"]["on_exists"]))
    client = InegiClient(http_client=HttpClient(file_policy=policy))

    client.download_zip_member(
        url=dataset["url"],
        member=dataset["state_member"],
        destination=raw_file,
    )
    print(f"{raw_file} ({raw_file.stat().st_size / 1e6:.0f} MB)")
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## Extracción
    Validamos las rutas igual que el job de procesamiento del DENUE, para que un
    nombre como `../../algo` no escriba fuera de `data/interim/` (Zip Slip).
    """)
    return


@app.cell
def _(Path, zipfile):
    def safe_extract(archive: zipfile.ZipFile, destination: Path) -> None:
        # Rechaza cualquier miembro cuya ruta final quede fuera del destino.
        root = destination.resolve()
        for member in archive.infolist():
            target = (root / member.filename).resolve()
            if root not in target.parents and target != root:
                raise ValueError(f"Ruta insegura en el zip: {member.filename}")
        archive.extractall(destination)

    return (safe_extract,)


@app.cell
def _(interim_dir, raw_file, safe_extract, zipfile):
    interim_dir.mkdir(parents=True, exist_ok=True)

    with zipfile.ZipFile(raw_file) as state_archive:
        safe_extract(state_archive, interim_dir)

    for extracted in sorted(interim_dir.rglob("*")):
        if extracted.is_file():
            print(extracted.relative_to(interim_dir))
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## Metadatos y catálogo
    Cada archivo del paquete usa su propia codificación: los metadatos vienen en
    ISO-8859-1 (como el resto de los productos del INEGI), mientras que el catálogo
    CSV y la capa `.shp` están en UTF-8.
    """)
    return


@app.cell
def _(interim_dir):
    metadata_file = next((interim_dir / "metadatos").glob("metadatos_dcah_*.txt"))
    metadata_text = metadata_file.read_text(encoding="latin-1")
    print(metadata_text[:1500])
    return


@app.cell
def _(interim_dir, pd):
    # El catálogo trae los mismos atributos que la capa, sin geometría. Ojo: aunque
    # viene dentro del ZIP de Sonora, es el catálogo nacional, y a diferencia de los
    # metadatos está en UTF-8.
    catalog = pd.read_csv(interim_dir / "catalogos" / "asentamientos_humanos.csv", dtype=str)
    print(catalog.shape)
    print(catalog["cve_ent"].nunique(), "entidades en el catálogo")
    catalog.head()
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## Lectura de la capa de asentamientos
    La capa `26as` (asentamientos de Sonora) usa **EPSG:6372**: Cónica Conforme de
    Lambert sobre ITRF2008, en **metros**. Es la proyección oficial del INEGI para
    todo México y sirve para calcular áreas; para mapas web o para cruzar con
    latitud/longitud hay que convertir a **EPSG:4326**.
    """)
    return


@app.cell
def _(gpd, interim_dir):
    settlements = gpd.read_file(interim_dir / "conjunto_de_datos" / "26as.shp")

    print(settlements.shape)
    print(settlements.crs.name, "| EPSG:", settlements.crs.to_epsg())
    settlements.head()
    return (settlements,)


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## Hermosillo
    Filtramos por clave de municipio (`030`) en vez de por nombre, y renombramos las
    columnas a inglés. La localidad `0001` es la ciudad; `0137` es Bahía de Kino y
    `0343`, Miguel Alemán.
    """)
    return


@app.cell
def _(settlements):
    HERMOSILLO_MUNICIPALITY = "030"

    columns = {
        "cvegeo": "geo_code",
        "cve_ent": "state_code",
        "cve_mun": "municipality_code",
        "cve_loc": "locality_code",
        "cve_asen": "settlement_code",
        "cp": "postal_code",
        "fecha_act": "updated_at",
        "institucio": "source_institution",
        "nom_asen": "settlement_name",
        "tipo": "settlement_type",
        "geometry": "geometry",
    }

    hermosillo = (
        settlements[settlements["cve_mun"] == HERMOSILLO_MUNICIPALITY]
        .rename(columns=columns)
        .set_geometry("geometry")
    )
    # Área en km², válida porque EPSG:6372 está en metros.
    hermosillo["area_km2"] = hermosillo.area / 1e6

    print(f"{len(hermosillo)} asentamientos en Hermosillo")
    hermosillo.drop(columns="geometry").head()
    return (hermosillo,)


@app.cell
def _(hermosillo):
    # Cuántos asentamientos por localidad, por tipo y por fecha de actualización.
    print(hermosillo["locality_code"].value_counts().to_string(), end="\n\n")
    print(hermosillo["settlement_type"].value_counts().to_string(), end="\n\n")
    print(hermosillo[["updated_at", "source_institution"]].value_counts().to_string())
    return


@app.cell
def _(hermosillo):
    # El código postal "00000" indica que el municipio no lo reportó.
    missing_postal_code = (hermosillo["postal_code"] == "00000").sum()
    print(f"Sin código postal: {missing_postal_code} de {len(hermosillo)}")

    hermosillo["area_km2"].describe()
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## ¿Aparecen las colonias de los avisos?
    Los avisos de Agua de Hermosillo mencionan colonias con variaciones de acentos
    y mayúsculas ("MISION DEL ARCO", "Misión del Arco"). Normalizamos los nombres
    (sin acentos, en mayúsculas, sin espacios repetidos) y buscamos algunas colonias
    tomadas de publicaciones reales.
    """)
    return


@app.cell
def _(re, unicodedata):
    def normalize_name(name: str) -> str:
        # Quita acentos y puntuación, y unifica mayúsculas y espacios para comparar nombres.
        ascii_name = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode()
        return " ".join(re.sub(r"[^A-Za-z0-9 ]", " ", ascii_name).upper().split())

    return (normalize_name,)


@app.cell
def _(hermosillo, normalize_name, pd):
    city = hermosillo[hermosillo["locality_code"] == "0001"].copy()
    city["settlement_key"] = city["settlement_name"].map(normalize_name)

    # Colonias mencionadas en avisos de Facebook (texto y OCR de las imágenes).
    mentioned = [
        "Bachoco",
        "MISION DEL ARCO",
        "Villa de Seris",
        "Pueblitos",
        "Olivos",
        "Castelina",
        "Nuevo Hermosillo",
        "Altares",
        "Sahuaro",
        "Modelo",
    ]

    matches = pd.DataFrame(
        [
            {
                "mentioned": name,
                "exact_match": (city["settlement_key"] == normalize_name(name)).any(),
                "partial_matches": city.loc[
                    city["settlement_key"].str.contains(normalize_name(name), regex=False),
                    "settlement_name",
                ].tolist(),
            }
            for name in mentioned
        ]
    )
    matches
    return city, mentioned


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    Las coincidencias exactas no bastan: algunas colonias vienen partidas en secciones
    ("Pueblitos Sección los Álamos", "Sahuaro Final") y otras comparten palabra con
    colonias distintas ("Los Olivos" y "Cuatro Olivos"). Al emparejar los avisos
    habrá que decidir la granularidad: sección exacta o colonia "madre".

    ## Mapa de la ciudad
    """)
    return


@app.cell
def _(city, mentioned, normalize_name, plt):
    mentioned_keys = [normalize_name(name) for name in mentioned]
    is_mentioned = city["settlement_key"].apply(
        lambda key: any(mentioned_key in key for mentioned_key in mentioned_keys)
    )

    fig_map, ax_map = plt.subplots(figsize=(8, 8))
    city.plot(ax=ax_map, color="#e1e0d9", edgecolor="#ffffff", linewidth=0.3)
    city[is_mentioned].plot(ax=ax_map, color="#2a78d6", edgecolor="#ffffff", linewidth=0.3)
    ax_map.set_title("Colonias de Hermosillo (DCAH 2025) · en azul, las mencionadas en avisos")
    ax_map.set_axis_off()
    fig_map
    return


@app.cell
def _(city, plt):
    # Las colonias más grandes suelen ser parques industriales o zonas en desarrollo;
    # conviene tenerlas ubicadas antes de normalizar quejas por área.
    largest = city.nlargest(12, "area_km2").set_index("settlement_name")["area_km2"].sort_values()

    fig_area, ax_area = plt.subplots(figsize=(8, 5))
    largest.plot.barh(ax=ax_area, color="#2a78d6")
    ax_area.set_xlabel("Área (km²)")
    ax_area.set_ylabel("")
    ax_area.set_title("Asentamientos más extensos de la ciudad")
    fig_area
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## Hallazgos y siguientes pasos
    - El DCAH 2025 cubre Hermosillo con polígonos de colonias actualizados por
      Catastro municipal: es la capa base para el mapa del tablero.
    - Los nombres requieren normalización y reglas para secciones y etapas antes de
      cruzarlos con los avisos de Facebook.
    - Los avisos casi nunca nombran colonias sino cruces de calles; ubicarlos es el
      tema de `02-job-ingestion-calles-mg.py`, que usa las colonias extraídas aquí.
    - Siguiente: convertir esta exploración en un job (`ingest_dcah_job`), y cruzar
      los polígonos con las AGEB del Marco Geoestadístico para obtener la población
      por colonia y normalizar las afectaciones por habitante.
    """)
    return


if __name__ == "__main__":
    app.run()
