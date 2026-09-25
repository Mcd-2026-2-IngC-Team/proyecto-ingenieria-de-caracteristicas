import pandas as pd
from pathlib import Path
import geopandas as gpd

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
        df = df[df["NOM_MUNM"] == "HERMOSILLO"].copy()

    return df[columnas].copy()    

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