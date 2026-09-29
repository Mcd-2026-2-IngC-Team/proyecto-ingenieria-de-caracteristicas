import ast
import time
from pathlib import Path
from urllib.parse import unquote

import pandas as pd
import requests
from bs4 import BeautifulSoup


from project_name.config import load_dataset_config, load_logging, load_params
from project_name.logging import log_execution
from pathlib import Path


# ============================================================
# Configuración
# ============================================================

params = load_params()
dataset = load_dataset_config(
    params,
    source="bachometro",
    dataset="baches",
)
processed_directory = Path(dataset["processed"]["directory"])

INPUT_CSV = (
    processed_directory
    / "baches_hermosillo.csv"
)

OUTPUT_CSV = (
    processed_directory
    / "relacion_colonia_baches_id.csv"
)

print("CWD:", Path.cwd())
print("INPUT:", INPUT_CSV)
print("ABSOLUTE:", INPUT_CSV.resolve())
print("EXISTS:", INPUT_CSV.exists())

# INPUT_CSV = Path("data/processed/bachometro/baches_hermosillo.csv")
# OUTPUT_CSV = Path("data/processed/bachometro/relacion_colonia_baches_id.csv")

URL = "https://bachometro.hermosillo.gob.mx/mapa/informacion/ajax"

# IMPORTANTE:
# Estas cookies expiran. Reemplázalas cuando sea necesario.
SESSION_COOKIE = "eyJpdiI6InNSWFZVM0VRU2NxRm5SeTNic0ZUVWc9PSIsInZhbHVlIjoiLzV5K3Z4UmUzcy9HM0FxTWE0R09Wc2RUaEo5Q3dUc0JrdWV5Vkt5KzBTNEJpNVhvSmZJS2ZZMjdJQ0JQdWJOd2ZzSVFhVTdPTElHdEl1bkpycWR5aUo4dmVGZFJSNUN4TG4wTGNxZCtWU2pYNmNCZjZEYzRCN0RHTE5QaDJQRlIiLCJtYWMiOiIwYWMxMDRlMDE2NmFjZGQ5NDcwZjNmMDQ4MTliNmQ0MTQ2YjA4NWI2M2ZjZDgwM2YyY2FhNDIyZTVhYmFmMGQ2IiwidGFnIjoiIn0%3D"

XSRF_TOKEN = "eyJpdiI6IlZGa1pId0lYYnBCaldXQzNHbFdIYVE9PSIsInZhbHVlIjoiTjF0SVJtYW5EaDBlNmoxNEJPRVpZZUpsZWtJN052RnBJb04yd1ZRQ2VWRUJzbTFYWmlEOHFaTmk1TnJPeVQvTHVwRzd4TlNjMEM5clI5eitwc09FcUxnSjRTS0wySWk5NEhoMThBcjJNVHB3NDJQR0gyMHh6THBhRldaYjhaRDkiLCJtYWMiOiIyYjUzOWU0ZDkxOTU1NDU2N2IwZDlkNzVkOTQwZmQxN2IyZmZmNzI2YzRhZDBiYjBiZjkxNDNmNTk2YTc2Yjc4IiwidGFnIjoiIn0%3D"


# ============================================================
# Crear sesión HTTP
# ============================================================

def create_session():
    """
    Crea una sesión de requests con las cookies necesarias
    para consultar el endpoint del Bachómetro.
    """

    session = requests.Session()

    session.cookies.set(
        "bachometro_hermosillo_session",
        SESSION_COOKIE,
        domain="bachometro.hermosillo.gob.mx",
    )

    session.cookies.set(
        "XSRF-TOKEN",
        XSRF_TOKEN,
        domain="bachometro.hermosillo.gob.mx",
    )

    return session


# ============================================================
# Parsear HTML
# ============================================================

def parse_neighborhood_info(neighborhood_id, html):
    """
    Extrae material, calle y colonia del HTML regresado
    por el endpoint.

    Ejemplo de dirección:

        Bv. Ignacio Soto 19-S,
        Zona Industrial Ferrocarril,
        83013 Hermosillo,
        Son.,
        México

    Resultado:

        material = Asfalto
        calle = Bv. Ignacio Soto 19-S
        colonia = Zona Industrial Ferrocarril
    """

    soup = BeautifulSoup(html, "html.parser")

    paragraphs = soup.select("p.card-text")

    material = None
    calle = None
    colonia = None

    for paragraph in paragraphs:
        text = paragraph.get_text(" ", strip=True)

        # ----------------------------------------
        # Material
        # ----------------------------------------
        # Ejemplo:
        # hace 4 años | Folio: 34095 | Material: Asfalto

        if "Material:" in text:
            material = text.split("Material:", 1)[1].strip()

        # ----------------------------------------
        # Dirección
        # ----------------------------------------
        # Ejemplo:
        # Bv. Ignacio Soto 19-S,
        # Zona Industrial Ferrocarril,
        # 83013 Hermosillo,
        # Son.,
        # México

        elif "," in text and "Colonias:" not in text:

            parts = [
                part.strip()
                for part in text.split(",")
            ]

            if len(parts) >= 1:
                calle = parts[0]

            if len(parts) >= 2:
                colonia = parts[1]

    return {
        "neighborhood_id": neighborhood_id,
        "material": material,
        "calle": calle,
        "colonia": colonia,
    }


# ============================================================
# Consultar información de un ID
# ============================================================

def get_neighborhood_info(session, neighborhood_id):
    """
    Consulta el endpoint del Bachómetro utilizando
    neighborhood_id como parámetro dinámico.
    """

    response = session.post(
        URL,
        data={
            "id": neighborhood_id,
        },
        headers={
            "X-Requested-With": "XMLHttpRequest",
            "X-XSRF-TOKEN": unquote(XSRF_TOKEN),
            "Referer": "https://bachometro.hermosillo.gob.mx/mapa",
        },
        timeout=30,
    )

    response.raise_for_status()

    return parse_neighborhood_info(
        neighborhood_id,
        response.text,
    )


# ============================================================
# Extraer IDs del CSV
# ============================================================

def extract_neighborhood_ids(df):
    """
    Lee la columna 'neighborhoods' y obtiene todos los IDs.

    Soporta valores como:

        [1224, 1225, 1226]

    o:

        "[1224, 1225, 1226]"

    También elimina IDs duplicados.
    """

    neighborhood_ids = set()

    for value in df["neighborhoods"].dropna():

        # ----------------------------------------
        # Si viene como string
        # ----------------------------------------

        if isinstance(value, str):

            try:
                parsed = ast.literal_eval(value)

                if isinstance(parsed, (list, tuple, set)):
                    neighborhood_ids.update(parsed)

                else:
                    neighborhood_ids.add(parsed)

            except (ValueError, SyntaxError):

                # Por si el valor es simplemente:
                # "1224"

                try:
                    neighborhood_ids.add(int(value))

                except ValueError:
                    print(
                        f"No se pudo interpretar "
                        f"neighborhoods: {value}"
                    )

        # ----------------------------------------
        # Si ya es un número
        # ----------------------------------------

        elif isinstance(value, (int, float)):

            neighborhood_ids.add(int(value))

        # ----------------------------------------
        # Si ya es una lista
        # ----------------------------------------

        elif isinstance(value, (list, tuple, set)):

            neighborhood_ids.update(value)

    # Convertimos todo a int y ordenamos
    return sorted(
        int(neighborhood_id)
        for neighborhood_id in neighborhood_ids
    )


# ============================================================
# Job
# ============================================================

def main():

    # print(f"Leyendo archivo: {INPUT_CSV}")

    # --------------------------------------------------------
    # Leer CSV
    # --------------------------------------------------------

    df = pd.read_csv(INPUT_CSV)

    if "neighborhoods" not in df.columns:
        raise ValueError(
            "El CSV no contiene una columna "
            "llamada 'neighborhoods'."
        )

    # --------------------------------------------------------
    # Obtener IDs únicos
    # --------------------------------------------------------

    neighborhood_ids = extract_neighborhood_ids(df)

    total = len(neighborhood_ids)

    print(
        f"Se encontraron {total} "
        "neighborhood IDs únicos."
    )

    # --------------------------------------------------------
    # Crear sesión
    # --------------------------------------------------------

    session = create_session()

    results = []

    # --------------------------------------------------------
    # Procesar IDs
    # --------------------------------------------------------

    for index, neighborhood_id in enumerate(
        neighborhood_ids,
        start=1,
    ):

        print(
            f"[{index}/{total}] "
            f"Procesando ID {neighborhood_id}"
        )

        try:

            info = get_neighborhood_info(
                session,
                neighborhood_id,
            )

            results.append(info)

            # print(
            #     f"    Material: {info['material']} | "
            #     f"Calle: {info['calle']} | "
            #     f"Colonia: {info['colonia']}"
            # )

        except requests.RequestException as error:

            # print(
            #     f"    Error obteniendo ID "
            #     f"{neighborhood_id}: {error}"
            # )

            results.append(
                {
                    "neighborhood_id": neighborhood_id,
                    "material": None,
                    "calle": None,
                    "colonia": None,
                }
            )

        # Pequeña pausa para no saturar el servidor
        time.sleep(0.2)

    # --------------------------------------------------------
    # Crear DataFrame
    # --------------------------------------------------------

    output_df = pd.DataFrame(
        results,
        columns=[
            "neighborhood_id",
            "material",
            "calle",
            "colonia",
        ],
    )

    # --------------------------------------------------------
    # Guardar CSV
    # --------------------------------------------------------

    OUTPUT_CSV.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    output_df.to_csv(
        OUTPUT_CSV,
        index=False,
        encoding="utf-8",
    )

    # --------------------------------------------------------
    # Resumen
    # --------------------------------------------------------

    print()
    print("Proceso terminado.")
    print(f"Archivo generado: {OUTPUT_CSV}")
    print(f"Registros generados: {len(output_df)}")


# ============================================================
# Entry point
# ============================================================

if __name__ == "__main__":
    main()