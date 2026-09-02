import pandas as pd

from project_name.features import build_denue_features


def make_raw_df(**overrides):
    row = {
        "id": 1,
        "nom_estab": "ABARROTES LUPITA",
        "codigo_act": 112511,
        "nombre_act": "Camaronicultura",
        "per_ocu": "31 a 50 personas",
        "municipio": "Hermosillo",
        "localidad": "Hermosillo",
        "latitud": 29.1,
        "longitud": -110.9,
        "telefono": "6621234567",
        "correoelec": "foo@example.com",
        "fecha_alta": "2010-07",
    }
    row.update(overrides)
    return pd.DataFrame([row])


def test_build_denue_features_selects_and_renames_relevant_columns():
    denue = build_denue_features(make_raw_df())

    assert list(denue.columns) == [
        "id",
        "business_name",
        "activity_code",
        "activity_name",
        "employee_range",
        "municipality",
        "locality",
        "latitude",
        "longitude",
        "registration_date",
        "employee_range_rank",
        "has_phone",
        "has_email",
    ]


def test_build_denue_features_ranks_employee_range_by_size():
    df = pd.concat(
        [
            make_raw_df(id=1, per_ocu="251 y más personas"),
            make_raw_df(id=2, per_ocu="0 a 5 personas"),
        ],
        ignore_index=True,
    )

    denue = build_denue_features(df)

    assert denue.set_index("id")["employee_range_rank"].to_dict() == {1: 7, 2: 1}


def test_build_denue_features_parses_dates_with_space_instead_of_hyphen():
    """Regression: some raw rows use "2013 07" instead of "2013-07"."""
    denue = build_denue_features(make_raw_df(fecha_alta="2013 07"))

    assert denue.loc[0, "registration_date"] == pd.Timestamp("2013-07-01")


def test_build_denue_features_flags_contact_info_presence_instead_of_raw_value():
    df = pd.concat(
        [
            make_raw_df(id=1, telefono="6621234567", correoelec="foo@example.com"),
            make_raw_df(id=2, telefono=None, correoelec=None),
        ],
        ignore_index=True,
    )

    denue = build_denue_features(df)

    assert denue.set_index("id")[["has_phone", "has_email"]].to_dict("index") == {
        1: {"has_phone": True, "has_email": True},
        2: {"has_phone": False, "has_email": False},
    }
    assert "phone" not in denue.columns
    assert "email" not in denue.columns
