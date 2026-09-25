import pandas as pd
from pathlib import Path
import geopandas as gpd

DENUE_COLUMNS = {
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

EMPLOYEE_RANGE_RANK = {
    "0 a 5 personas": 1,
    "6 a 10 personas": 2,
    "11 a 30 personas": 3,
    "31 a 50 personas": 4,
    "51 a 100 personas": 5,
    "101 a 250 personas": 6,
    "251 y más personas": 7,
}

SUBC_COLUMNS_HL = [
    "geometry",
    "ID",
    "CVE_SUBC",
    "CONDICION",
    "ORDER_1",
    "ID_DRENA"
]

SUBC_COLUMNS_DR = [
    "geometry",
    "ID",
    "CVE_SUBC",
    "CONDICION",
    "ID_DRENA",
    "ARBSUM"
]

SUBC_COLUMNS_SUBC = [
    "geometry",
    "ID",
    "CVE_SUBCUE"
]

SUBC_COLUMNS_HA = [
    "geometry",
    "IDBD",
    "FC",
    "CONDICION"
]

SUBC_COLUMNS_TO = [
    "geometry",
    "FC",
    "CLASE",
    "TERMINO_GE",
    "NOMBRE"
]

#Tenemos un diccionario de sufijos y sus correspondientes columnas utiles
SUBC_COLUMNAS_UTILES = {
    "_hl": SUBC_COLUMNS_HL,
    "_dr": SUBC_COLUMNS_DR,
    "_subc": SUBC_COLUMNS_SUBC,
    "_ha": SUBC_COLUMNS_HA,
    "_to": SUBC_COLUMNS_TO
}


def cargar_capa(ruta_subcuenca: str | Path, sufijo: str, columnas: list[str])-> gpd.GeoDataFrame:
    print(ruta_subcuenca)
    archivo = list(ruta_subcuenca.glob(f"*{sufijo}.shp"))[0]

    df = gpd.read_file(archivo)

    if sufijo == "_to":
        df = df[df["NOM_MUNM"] == "Hermosillo"].copy()

    return df[columnas].copy()    


def build_denue_features(df: pd.DataFrame) -> pd.DataFrame:
    denue = df[list(DENUE_COLUMNS)].rename(columns=DENUE_COLUMNS)

    # Un par de valores usan espacio en vez de guion (ej. "2013 07"); los normalizamos.
    registration_date = denue["registration_date"].str.replace(" ", "-", regex=False)

    return denue.assign(
        employee_range_rank=denue["employee_range"].map(EMPLOYEE_RANGE_RANK),
        registration_date=pd.to_datetime(registration_date, format="%Y-%m"),
        # La mayoría de los registros no tienen teléfono/correo; la presencia
        # es una señal más útil que el valor crudo.
        has_phone=denue["phone"].notna(),
        has_email=denue["email"].notna(),
    ).drop(columns=["phone", "email"])


def build_subcuencas_features(nombre_subcuenca: str, ruta_subcuenca: str | Path) -> pd.DataFrame:
    #Crearemos un diccionario anidado en dataframes, contendra nombre_subcuenta -> sufijo -> datafram_limpio
    dataframes = {}

    dataframes[nombre_subcuenca] = {}

    for sufijo, columnas in SUBC_COLUMNAS_UTILES.items():
        dataframes[nombre_subcuenca][sufijo] = cargar_capa(
            ruta_subcuenca,
            sufijo,
            columnas
        )

    return dataframes