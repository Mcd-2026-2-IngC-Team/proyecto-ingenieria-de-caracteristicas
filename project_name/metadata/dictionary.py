"""Diccionario de datos: un archivo por cada dataset procesado, en CSV (references/,
para que GitHub lo renderice como tabla) y en JSON (references/json/).

Lo único escrito a mano son las descripciones de abajo; el tipo, los nulos, los valores
distintos y el rango los calcula pandas (dtype, isna, nunique, min/max) al generar los
archivos.

    uv run python -m project_name.metadata.dictionary
"""

import csv
from datetime import UTC, datetime
import json
from pathlib import Path

from loguru import logger
import pandas as pd
import geopandas as gpd

from project_name.config import PROJECT_ROOT, load_logging, load_params
from project_name.constants import REFERENCES_DIR
from project_name.logging import log_execution
from project_name.jobs.process_subcuencas_job import leer_capa

REFERENCES_JSON_DIR = REFERENCES_DIR / "json"

# El rango (min/max) de una columna de texto libre expondría valores reales sin
# agregar, así que solo se publica para columnas que no son de texto. pandas 3 usa un
# dtype de texto dedicado (se imprime "str"), no "object", así que el tipo se detecta
# con is_string_dtype en vez de comparar el nombre del dtype.
TEXT_RANGE_NOTE = (
    "El rango de las columnas de texto no se publica: su mínimo y su máximo serían "
    "valores reales sin agregar."
)

# Qué representa una fila de cada dataset procesado (la "granularidad" de la tabla).
ROWS = {
    "publicaciones_aguah": (
        "una publicación de la página oficial de Agua de Hermosillo en Facebook"
    ),
    "colonias_hermosillo": "un asentamiento humano de Hermosillo según el DCAH 2025 del INEGI",
    "ubicaciones_aviso": "un lugar mencionado en una publicación de Agua de Hermosillo",
    "baches": "un reporte ciudadano de bache en el Bachómetro de Hermosillo",
}

# Columnas que deben leerse como fecha: pandas no las infiere solo desde un CSV, así
# que se declaran a mano, igual que ROWS y DESCRIPTIONS.
DATE_COLUMNS = {
    "publicaciones_aguah": ["published_at", "announced_start_at"],
    "colonias_hermosillo": [],
    "ubicaciones_aviso": [],
    "baches": ["date"],
}

DESCRIPTIONS = {
    "publicaciones_aguah": {
        "post_id": "Identificador de la publicación en Facebook; llave primaria",
        "source_slug": "Rango de fechas del export del scraper del que salió la fila",
        "published_at": "Fecha y hora de publicación en hora local de Hermosillo (UTC-7)",
        "year": "Año de publicación",
        "month": "Mes de publicación, de 1 a 12",
        "iso_week": "Semana ISO de publicación, de 1 a 53",
        "day_of_week": "Día de la semana de publicación, de 0 (lunes) a 6 (domingo)",
        "hour_of_day": "Hora del día de publicación, de 0 a 23",
        "text": "Texto del cuerpo de la publicación; vacío si la publicación no trae texto",
        "has_text": "Si la publicación trae texto en el cuerpo",
        "ocr_text": (
            "Texto extraído por OCR (PaddleOCR-VL) de la imagen de la publicación; "
            "vacío si no hay imagen o si el OCR no encontró texto"
        ),
        "ocr_status": "Resultado del OCR: ocr_success o skipped_no_image",
        "has_image": "Si la publicación trae imagen",
        "reactions_like": "Reacciones 'me gusta'",
        "reactions_love": "Reacciones 'me encanta'",
        "reactions_haha": "Reacciones 'me divierte'",
        "reactions_wow": "Reacciones 'me asombra'",
        "reactions_sad": "Reacciones 'me entristece'",
        "reactions_angry": "Reacciones 'me enoja'; es la señal de molestia ciudadana",
        "reactions_care": "Reacciones 'me importa'",
        "reactions_total": "Suma de todas las reacciones de la publicación",
        "angry_share": (
            "Proporción de enojo sobre el total de reacciones; nulo si no hubo reacciones"
        ),
        "comments_count": "Número de comentarios de la publicación",
        "shares_count": "Número de veces que se compartió la publicación",
        "likes_count": "Número de 'me gusta' que reporta el scraper aparte de las reacciones",
        "top_comment_text": (
            "Texto del comentario destacado por Facebook; sin el nombre de quien lo escribió"
        ),
        "top_comment_likes": "'Me gusta' del comentario destacado",
        "event_type": (
            "Tipo de evento por reglas sobre el texto y el OCR, en orden de prioridad: "
            "restablecimiento, corte_programado, emergencia, pipas u otro"
        ),
        "announced_start_at": (
            "Inicio de la afectación según lo anunciado; nulo si el aviso no declara fecha"
        ),
        "announced_duration_hours": (
            "Duración de la afectación en horas según lo anunciado; "
            "nulo si el aviso no declara un plazo"
        ),
    },
    "colonias_hermosillo": {
        "colonia_id": "Clave geoestadística del asentamiento (cvegeo del INEGI); llave primaria",
        "settlement_name": "Nombre del asentamiento tal como lo publica el INEGI",
        "settlement_name_normalized": (
            "Nombre sin acentos, signos ni minúsculas, para emparejarlo con los avisos"
        ),
        "settlement_type": "Tipo de asentamiento: COLONIA, FRACCIONAMIENTO, RESIDENCIAL...",
        "locality_code": (
            "Clave de localidad del INEGI, de cuatro dígitos: 0001 es la ciudad, "
            "0137 Bahía de Kino y 0343 Miguel Alemán. Léase como texto: en CSV pierde "
            "los ceros a la izquierda"
        ),
        "postal_code": "Código postal que reportó el municipio; 00000 si no lo reportó",
        "area_km2": "Área del polígono del asentamiento en kilómetros cuadrados",
        "centroid_lat": "Latitud del centroide del asentamiento (EPSG:4326)",
        "centroid_lon": "Longitud del centroide del asentamiento (EPSG:4326)",
        "updated_at": "Mes y año en que el municipio actualizó el asentamiento",
    },
    "ubicaciones_aviso": {
        "post_id": "Publicación donde se mencionó el lugar; une con publicaciones_aguah",
        "location_type": (
            "Cómo nombró el aviso el lugar: 'colonia' si dio el nombre del asentamiento, "
            "'cruce' si dio un cruce de calles"
        ),
        "raw_text": "El lugar tal como lo nombra la publicación, ya normalizado",
        "colonia_id": (
            "Asentamiento al que corresponde el lugar; une con colonias_hermosillo. "
            "Nulo cuando la mención no se pudo resolver"
        ),
        "source_field": (
            "Dónde se encontró la mención: 'texto' en el cuerpo de la publicación, "
            "'ocr' solo en el volante, 'ambos' si aparece en los dos"
        ),
        "lat": (
            "Latitud del cruce geocodificado (EPSG:4326). Nula en las filas de colonia: "
            "una colonia es un polígono, no un punto, y su geometría está en "
            "colonias_hermosillo"
        ),
        "lon": "Longitud del cruce geocodificado (EPSG:4326); nula en las filas de colonia",
        "match_method": (
            "Cómo se resolvió: colonia_con_marcador (el texto dice 'colonia X'), "
            "colonia_en_catalogo (el nombre aparece suelto, típico de las tablas de los "
            "volantes), cruce_geocodificado o unmatched. Es el indicador de confianza de "
            "la fila: las menciones con marcador explícito son más seguras que un nombre suelto"
        ),
    },
    "baches": {
        "id_row": "Identificador secuencial de la fila, asignado al combinar los años",
        "latitude": "Latitud del reporte de bache",
        "longitude": "Longitud del reporte de bache",
        "date": "Fecha del reporte de bache",
        "neighborhoods": "IDs de la(s) colonia(s) del Bachómetro asociadas al reporte",
        "material": "Código del tipo de material/pavimento reportado por el Bachómetro",
        "description": "Descripción en texto libre del reporte, escrita por el ciudadano",
        "id": "Identificador del reporte en el Bachómetro",
        "year": "Año de la fuente de datos, según bachometro.hermosillo.gob.mx",
        "date_mx": "Fecha del reporte en formato mexicano (dd/mm/aaaa)",
    },
}

DESCRIPTIONS_SUBCUENCAS = {
    "hl": {
        "geometry": "Geometría lineal del segmento de la red hidrográfica",
        "ID": "Identificador único del segmento de la red hidrográfica",
        "CVE_SUBC": "Clave de la subcuenca hidrográfica",
        "CONDICION": "Descripción de la condición del drenaje",
        "ORDER_1": "Magnitud de orden (clasificación de Strahler) a nivel de subcuenca",
        "ID_DRENA": "Identificador del punto de drenaje al que corresponde el segmento",
        "ENABLED": "Indicador que señala si el segmento está habilitado para formar parte de la red geométrica",
    },

    "dr": {
        "geometry": "Geometría puntual del punto de drenaje",
        "ID": "Identificador único del punto de drenaje",
        "CVE_SUBC": "Clave de la subcuenca hidrográfica",
        "CONDICION": "Descripción de la condición del drenaje",
        "ID_DRENA": "Identificador del punto de drenaje",
        "ARBSUM": "Sumatoria de las longitudes de las líneas de flujo aguas arriba que confluyen en el punto de drenaje",
    },

    "subc": {
        "geometry": "Geometría de la unidad de captación a nivel subcuenca",
        "ID": "Identificador único de la unidad de captación",
        "CVE_SUBCUE": "Clave de la Subcuenca Hidrográfica",
    },

    "ha": {
        "geometry": "Geometría poligonal del cuerpo de agua",
        "IDBD": "Identificador asociado al objeto geográfico en la base de datos",
        "FC": "Código de clasificación del objeto geográfico",
        "CONDICION": "Condición de permanencia del cuerpo de agua",
    },

    "to": {
        "geometry": "Geometría puntual del elemento geográfico",
        "FC": "Código de clasificación del elemento geográfico",
        "CLASE": "Clase a la que pertenece el elemento geográfico",
        "TERMINO_GE": "Término genérico que identifica el tipo de rasgo geográfico",
        "NOMBRE": "Nombre oficial del elemento geográfico",
    },
}

ROWS_SUBCUENCAS = {
    "hl": (
        "Un segmento de la red hidrográfica, que representa una sección "
        "lineal del cauce o flujo de agua dentro de la subcuenca."
    ),
    "dr": (
        "Un punto de drenaje, que representa una ubicación donde convergen "
        "o se conectan líneas de flujo de la red hidrográfica y por donde "
        "se concentra o continúa el drenaje del agua."
    ),
    "subc": (
        "Una unidad de captación a nivel subcuenca, que representa el área "
        "del territorio delimitada por la que se concentra y conduce el "
        "escurrimiento hacia una salida común."
    ),
    "ha": (
        "Un cuerpo de agua, que representa una superficie de agua delimitada "
        "espacialmente dentro de la subcuenca."
    ),
    "to": (
        "Un elemento geográfico con información toponímica, es decir, "
        "información relacionada con los nombres propios utilizados para "
        "identificar lugares o rasgos geográficos, dentro del municipio de "
        "Hermosillo."
    ),
}


def processed_files(params: dict) -> dict[str, Path]:
    """Mapea cada dataset con salida procesada a la ruta de su archivo, según params.yml."""
    files = {}
    for source in params["sources"].values():
        for key, dataset in source["datasets"].items():
            processed = dataset.get("processed")
            if processed:
                files[key] = Path(processed["directory"]) / processed["filename"]
    return files


def _format_range(non_null: pd.Series) -> str:
    minimum, maximum = non_null.min(), non_null.max()
    if isinstance(minimum, pd.Timestamp):
        return f"{minimum.date()} – {maximum.date()}"
    return f"{minimum} – {maximum}"


def profile(processed_file: Path, dataset: str, layer: str | None = None) -> tuple[int, list[dict]]:
    if processed_file.suffix == ".gpkg":
        df = leer_capa(processed_file, layer)
    else:
        """Filas del CSV y, por columna, su tipo, nulos, valores distintos y rango."""
        df = pd.read_csv(processed_file, parse_dates=DATE_COLUMNS.get(dataset, []))

    columns = []
    for name in df.columns:
        series = df[name]

        if name == "geometry":
            columns.append(
                {
                    "column_name": name,
                    "type": "geometry",
                    "nulos_pct": float(series.isna().mean() * 100),
                    "distintos": None,
                    "rango": None,
                    "is_text": False,
                }
            )
            continue
    
        non_null = series.dropna()
        is_text = pd.api.types.is_string_dtype(series.dtype)
        columns.append(
            {
                "column_name": name,
                "type": str(series.dtype),
                "nulos_pct": float(series.isna().mean() * 100),
                # nunique() es un conteo exacto, no una estimación: en un diccionario de
                # datos eso importa, p. ej. para ver que una llave no se repite.
                "distintos": int(series.nunique(dropna=True)),
                "rango": None if is_text or non_null.empty else _format_range(non_null),
                "is_text": is_text,
            }
        )
    return len(df), columns


def document(dataset: str, processed_file: Path, n_rows: int | dict[str, int], columns: list[dict]) -> dict:
    """Construye el diccionario de un dataset CSV o de un GeoPackage."""

    #descriptions = DESCRIPTIONS[dataset]
    #row_description = ROWS[dataset]

    shown = (
        processed_file.relative_to(PROJECT_ROOT) if processed_file.is_relative_to(PROJECT_ROOT) else processed_file
    )

    # Convertir explícitamente a formato POSIX, porque queremos 
    # que los diccionarios sean reproducibles independientemente 
    # de si se generan en Windows o Linux
    shown = shown.as_posix()

    if processed_file.suffix == ".gpkg":
        row_description = ROWS_SUBCUENCAS

        documented_columns = [
            {
                "capa": column["capa"],
                "nombre": column["column_name"],
                "tipo": column["type"],
                "nulos_pct": column["nulos_pct"],
                "distintos": column["distintos"],
                "rango": column["rango"],
                "descripcion": DESCRIPTIONS_SUBCUENCAS[
                    column["capa"]
                ][column["column_name"]],
            }
            for column in columns
        ]
    else:
        row_description = ROWS[dataset]

        documented_columns = [
            {
                "nombre": column["column_name"],
                "tipo": column["type"],
                "nulos_pct": column["nulos_pct"],
                "distintos": column["distintos"],
                "rango": column["rango"],
                "descripcion": DESCRIPTIONS[
                    dataset
                ][column["column_name"]],
            }
            for column in columns
        ]

    documented = {
        "dataset": dataset,
        "archivo": str(shown),
        "una_fila_es": row_description,
        "filas": n_rows,
        "columnas": documented_columns,
        "generado": {
            "fecha": datetime.now(UTC).strftime("%Y-%m-%d %H:%M UTC"),
            "comando": "make dictionary",
            "perfil": "pandas: dtype, isna(), nunique(), min()/max()",
        },
    }
    if any(column["is_text"] for column in columns):
        documented["nota"] = TEXT_RANGE_NOTE

    return documented


def write_csv(destination: Path, columns: list[dict],is_geopackage: bool = False,) -> None:
    fieldnames = ["nombre", "tipo", "nulos_pct", "distintos", "rango", "descripcion"]

    if is_geopackage:
        fieldnames.insert(0, "capa")

    with destination.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(columns)

def profile_processed_file(dataset: str,processed_file: Path,is_geopackage: bool,) -> tuple[int | dict[str, int], list[dict]]:
    """Perfila y valida un archivo CSV o un GeoPackage procesado."""

    if is_geopackage:

        layers = gpd.list_layers(processed_file)["name"].tolist()

        all_columns = []
        rows_by_layer = {}

        for layer in layers:
            if layer not in DESCRIPTIONS_SUBCUENCAS:
                raise ValueError(f"{dataset}: falta describir sus columnas {layer} en dictionary.py")
                
            n_rows, columns = profile(processed_file, dataset, layer)
            rows_by_layer[layer] = n_rows

            for column in columns:
                column["capa"] = layer

            all_columns.extend(columns)

            validate_columns(
                dataset,
                columns,
                DESCRIPTIONS_SUBCUENCAS[layer],
            )

        return rows_by_layer, all_columns

    if dataset not in DESCRIPTIONS:
        raise ValueError(f"{dataset}: falta describir sus columnas en dictionary.py")
    
    n_rows, columns = profile(processed_file, dataset)

    validate_columns(
        dataset,
        columns,
        DESCRIPTIONS[dataset],
    )

    return n_rows, columns

@log_execution
def build_dictionaries(params: dict) -> list[Path]:
    """Escribe un diccionario (CSV + JSON) por dataset procesado y devuelve las rutas.

    Falla si una columna no está descrita, o si se describe una que ya no existe: es lo
    que evita que el diccionario se quede atrás cuando cambian los datos.
    """
    REFERENCES_DIR.mkdir(parents=True, exist_ok=True)
    REFERENCES_JSON_DIR.mkdir(parents=True, exist_ok=True)

    written = []
    for dataset, processed_file in processed_files(params).items():
        if not processed_file.exists():
            raise FileNotFoundError(f"{processed_file} not found: run `make data` first")
        is_geopackage = processed_file.suffix == ".gpkg"

        n_rows, columns = profile_processed_file(dataset,processed_file,is_geopackage)

        documented = document(dataset,processed_file,n_rows,columns)

        json_destination = REFERENCES_JSON_DIR / f"diccionario_{dataset}.json"
        json_destination.write_text(
            json.dumps(documented, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )

        csv_destination = REFERENCES_DIR / f"{dataset}.csv"
        write_csv(csv_destination, documented["columnas"],is_geopackage)

        n_columns = len(documented["columnas"])

        logger.info(
            "Documented {} columns → {}, {}", n_columns, csv_destination, json_destination
        )
        written += [csv_destination, json_destination]

    return written

def validate_columns(dataset: str,columns: list[dict],descriptions: dict[str, str],) -> None:
    """Valida que las columnas tengan una descripción y que no sobren descripciones."""

    column_names = {column["column_name"] for column in columns}
    description_names = set(descriptions)

    undocumented = column_names - description_names
    missing = description_names - column_names

    if undocumented or missing:
        raise ValueError(
            f"{dataset}: columnas sin describir: {sorted(undocumented)}; "
            f"descritas pero inexistentes: {sorted(missing)}"
        )

def main() -> None:
    params = load_params()
    load_logging(
        level=params["logging"]["level"],
        log_file=Path(params["logging"]["file"]),
        console=params["logging"].get("console", False),
    )

    for destination in build_dictionaries(params):
        print(f"diccionario → {destination.relative_to(PROJECT_ROOT)}")


if __name__ == "__main__":
    main()
