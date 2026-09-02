import pandas as pd

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
