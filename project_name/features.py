from pathlib import Path

import geopandas as gpd
import pandas as pd

SUBC_COLUMNS_HL = [
    "geometry",
    "ID",
    "CVE_SUBC",
    "CONDICION",
    "ORDER_1",
    "ID_DRENA",
    "ENABLED",
]

SUBC_COLUMNS_DR = ["geometry", "ID", "CVE_SUBC", "CONDICION", "ID_DRENA", "ARBSUM"]

SUBC_COLUMNS_SUBC = ["geometry", "ID", "CVE_SUBCUE"]

SUBC_COLUMNS_HA = ["geometry", "IDBD", "FC", "CONDICION"]

SUBC_COLUMNS_TO = ["geometry", "FC", "CLASE", "TERMINO_GE", "NOMBRE"]

# Tenemos un diccionario de sufijos y sus correspondientes columnas utiles
SUBC_COLUMNAS_UTILES = {
    "_hl": SUBC_COLUMNS_HL,
    "_dr": SUBC_COLUMNS_DR,
    "_subc": SUBC_COLUMNS_SUBC,
    "_ha": SUBC_COLUMNS_HA,
    "_to": SUBC_COLUMNS_TO,
}


# Tipos de incidente del 911 relacionados con inundación/agua, seleccionados a
# mano tras leer el catálogo completo (475 valores) en
# notebooks/AAMM/00-AAMM-data-exploration.ipynb. Esta constante es la fuente de
# verdad del ETL; la libreta conserva su propia copia como exploración.
GRUPOS_INCIDENTE_911 = {
    "inundacion_directa": [
        "INUNDACIONES",
        "INUNDACIÓN",
        "ENCHARCAMIENTO/ DESBORDAMIENTO DE RÍO",
        "DESLAVES",
    ],
    "fenomeno_hidrometeorologico": [
        "HURACANES- DAÑOS EN INFRAESTRUCTURA CASA HABITACIÓN",
        "HURACANES-AFECTACIÓN A VÍAS DE COMUNICACIÓN (CARRETERAS, PUENTES Y LÍNEAS DE FERROCARRIL)",
        "HURACANES-CAÍDA DE POSTES Y/O CABLES",
        "HURACANES- COLAPSO DE ESTRUCTURA O EDIFICACIÓN",
        "HURACANES-VEHÍCULO VARADO",
        "HURACANES-CAÍDA DE ÁRBOL",
        "HURACANES- SOLICITUD DE INFORMACIÓN CIUDADANA",
        "DAÑOS A VEHÍCULO POR FENÓMENOS NATURALES",
        "DAÑOS A INMUEBLE POR FENÓMENOS NATURALES",
        "DAÑOS POR CAÍDA DE RAYO",
    ],
    "drenaje_y_red_de_agua": [
        "ALCANTARILLA SIN TAPA",
        "ALCANTARILLA OBSTRUIDA",
        "ALCANTARILLA-REGISTRO SIN TAPA",
        "FUGA DE AGUA POTABLE",
        "FUGA DE AGUAS NEGRAS-NO POTABLES",
        "DESPERDICIO DE AGUA",
        "REPORTE DE AFECTACIÓN AL SUMINISTRO DE AGUA O  SISTEMA DE DRENAJE",
    ],
    "ahogamiento_acuaticos": [
        "AHOGAMIENTO",
        "AHOGAMIENTO-SUMERSIÓN",
        "NAUFRAGIO/HUNDIMIENTO/VARADURA DE EMBARCACIÓN",
        "ACCIDENTE ACUÁTICO CON LESIONADOS",
        "ACCIDENTE DE EMBARCACIONES CON LESIONADOS",
    ],
    "terreno": [
        "SOCAVÓN",
        "HUNDIMIENTOS / AGRIETAMIENTOS/ INESTABILIDAD DE LADERA",
        "HUNDIMIENTOS / AGRIETAMIENTOS EN SUELO/ INESTABILIDAD DE LADERA",
        "DERRUMBES",
        "ARBOL CAÍDO O POR CAER",
        "ÁRBOL CAÍDO O POR CAER",
        "VIALIDAD EN MAL ESTADO",
        "VIALIDAD EN MAL ESTADO-BACHES",
    ],
}

TIPOS_INCIDENTE_911_SELECCIONADOS = frozenset(
    tipo for tipos in GRUPOS_INCIDENTE_911.values() for tipo in tipos
)

INCIDENTE_A_GRUPO_911 = {
    tipo: grupo for grupo, tipos in GRUPOS_INCIDENTE_911.items() for tipo in tipos
}

COLUMNAS_LLAMADAS_911 = {
    "COLONIA": "colonia",
    "TIPO DE INCIDENTE": "tipo_incidente",
    "FECHA": "fecha",
    "HORA": "hora",
}


def load_llamadas_911(xlsx_path: str | Path) -> pd.DataFrame:
    """Lee el Excel de llamadas 911 (una hoja por año) y lo concatena en un solo DataFrame."""
    xlsx = pd.ExcelFile(xlsx_path, engine="calamine")
    return pd.concat((xlsx.parse(sheet) for sheet in xlsx.sheet_names), ignore_index=True)


def clean_llamadas_911(df: pd.DataFrame) -> pd.DataFrame:
    """Limpia las llamadas 911: quita nulos, conserva los tipos de incidente
    seleccionados, renombra columnas a snake_case y agrega grupo_incidente."""
    df = df.dropna()
    df = df[df["TIPO DE INCIDENTE"].isin(TIPOS_INCIDENTE_911_SELECCIONADOS)].copy()
    df = df.rename(columns=COLUMNAS_LLAMADAS_911)
    df["hora"] = df["hora"].astype(int)
    df["grupo_incidente"] = df["tipo_incidente"].map(INCIDENTE_A_GRUPO_911)
    return df.reset_index(drop=True)


def cargar_capa(ruta_subcuenca: str | Path, sufijo: str, columnas: list[str]) -> gpd.GeoDataFrame:
    print(ruta_subcuenca)
    archivo = next(iter(ruta_subcuenca.glob(f"*{sufijo}.shp")))

    df = gpd.read_file(archivo)

    if sufijo == "_to":
        df = df[df["NOM_MUNM"] == "HERMOSILLO"].copy()

    return df[columnas].copy()


def build_subcuencas_features(
    nombre_subcuenca: str, ruta_subcuenca: str | Path
) -> dict[str, dict[str, gpd.GeoDataFrame]]:
    # Crearemos un diccionario anidado en dataframes, contendra nombre_subcuenta -> sufijo -> datafram_limpio
    dataframes = {}

    dataframes[nombre_subcuenca] = {}

    for sufijo, columnas in SUBC_COLUMNAS_UTILES.items():
        dataframes[nombre_subcuenca][sufijo] = cargar_capa(ruta_subcuenca, sufijo, columnas)

    return dataframes
