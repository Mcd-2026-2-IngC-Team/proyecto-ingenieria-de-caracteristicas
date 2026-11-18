"""Reglas de calidad de los datasets procesados, una por dataset, con Pandera.

Solo viven aquí las reglas más sencillas u obvias: llaves únicas, rangos, catálogos
cerrados y coordenadas dentro de Hermosillo. `make validate` (y el final de `make data`)
las corre sobre data/processed/.
"""

from datetime import UTC, datetime

import pandera.pandas as pa

from project_name.features import GRUPOS_INCIDENTE_911
from project_name.hydro_context import CONTEXT_NAMES, PROXIMITY_LEVELS
from project_name.jobs.process_llamadas_911_job import TIPOS_INCIDENTE_EQUIVALENTES

# Caja amplia alrededor del municipio de Hermosillo (incluye Bahía de Kino e Isla
# Tiburón); basta para detectar coordenadas invertidas o de otro estado.
HERMOSILLO_BOUNDS = {"lat": (27.5, 30.5), "lon": (-113.0, -110.0)}

REACTIONS = ["like", "love", "haha", "wow", "sad", "angry", "care"]
COUNTS = [f"reactions_{name}" for name in REACTIONS] + [
    "reactions_total",
    "comments_count",
    "shares_count",
    "likes_count",
    "top_comment_likes",
]

COLONIA_ID = pa.Check.str_matches(r"\d{13}")


def _latitude(nullable: bool = False) -> pa.Column:
    return pa.Column(checks=pa.Check.in_range(*HERMOSILLO_BOUNDS["lat"]), nullable=nullable)


def _longitude(nullable: bool = False) -> pa.Column:
    return pa.Column(checks=pa.Check.in_range(*HERMOSILLO_BOUNDS["lon"]), nullable=nullable)


PUBLICACIONES_AGUAH = pa.DataFrameSchema(
    {
        "post_id": pa.Column(unique=True),
        "published_at": pa.Column(),
        # Vacíos, nunca nulos: si faltaba el texto lo dicen has_text y has_ocr_text.
        "text": pa.Column(),
        "ocr_text": pa.Column(),
        "top_comment_text": pa.Column(),
        "year": pa.Column(checks=pa.Check.in_range(2020, datetime.now(UTC).year)),
        "month": pa.Column(checks=pa.Check.in_range(1, 12)),
        "iso_week": pa.Column(checks=pa.Check.in_range(1, 53)),
        "day_of_week": pa.Column(checks=pa.Check.in_range(0, 6)),
        "hour_of_day": pa.Column(checks=pa.Check.in_range(0, 23)),
        **{column: pa.Column(checks=pa.Check.ge(0)) for column in COUNTS},
        "angry_share": pa.Column(checks=pa.Check.in_range(0, 1), nullable=True),
        "ocr_status": pa.Column(checks=pa.Check.isin(["ocr_success", "skipped_no_image"])),
        "event_type": pa.Column(
            checks=pa.Check.isin(
                ["restablecimiento", "corte_programado", "emergencia", "pipas", "otro"]
            )
        ),
        "announced_duration_hours": pa.Column(checks=pa.Check.gt(0), nullable=True),
    },
    checks=[
        pa.Check(
            lambda df: (
                df["reactions_total"] == df[[f"reactions_{n}" for n in REACTIONS]].sum(axis=1)
            ),
            name="reactions_total_is_sum_of_reactions",
        ),
        pa.Check(
            lambda df: df["has_ocr_text"] == df["ocr_text"].ne(""),
            name="has_ocr_text_matches_ocr_text",
        ),
        pa.Check(
            lambda df: df["has_announced_start_at"] == df["announced_start_at"].notna(),
            name="has_announced_start_at_matches_announced_start_at",
        ),
    ],
)

COLONIAS_HERMOSILLO = pa.DataFrameSchema(
    {
        "colonia_id": pa.Column(checks=COLONIA_ID, unique=True),
        "settlement_name": pa.Column(),
        "settlement_name_normalized": pa.Column(),
        "settlement_type": pa.Column(),
        "locality_code": pa.Column(checks=pa.Check.str_matches(r"\d{4}")),
        "postal_code": pa.Column(checks=pa.Check.str_matches(r"\d{5}")),
        "area_km2": pa.Column(checks=pa.Check.gt(0)),
        "centroid_lat": _latitude(),
        "centroid_lon": _longitude(),
    }
)

UBICACIONES_AVISO = pa.DataFrameSchema(
    {
        "post_id": pa.Column(),
        "raw_text": pa.Column(),
        "location_type": pa.Column(checks=pa.Check.isin(["colonia", "cruce"])),
        "source_field": pa.Column(checks=pa.Check.isin(["texto", "ocr", "ambos"])),
        "match_method": pa.Column(
            checks=pa.Check.isin(
                [
                    "colonia_con_marcador",
                    "colonia_en_catalogo",
                    "cruce_geocodificado",
                    "unmatched",
                ]
            )
        ),
        "colonia_id": pa.Column(checks=COLONIA_ID, nullable=True),
        "lat": _latitude(nullable=True),
        "lon": _longitude(nullable=True),
    },
    # Los nulos no son faltantes sueltos: los explica match_method.
    checks=[
        pa.Check(
            lambda df: (
                (df["lat"].notna() & df["lon"].notna())
                == df["match_method"].eq("cruce_geocodificado")
            ),
            name="point_only_for_geocoded_crossings",
        ),
        pa.Check(
            lambda df: df["colonia_id"].isna() == df["match_method"].eq("unmatched"),
            name="colonia_id_null_only_when_unmatched",
        ),
    ],
    unique=["post_id", "location_type", "raw_text"],
)

# Tipo canónico de incidente -> su grupo; las variantes ortográficas ya se unificaron.
GRUPO_DE_TIPO_911 = {
    tipo: grupo
    for grupo, tipos in GRUPOS_INCIDENTE_911.items()
    for tipo in tipos
    if tipo not in TIPOS_INCIDENTE_EQUIVALENTES
}

LLAMADAS_911_HERMOSILLO = pa.DataFrameSchema(
    {
        "colonia": pa.Column(),
        "tipo_incidente": pa.Column(checks=pa.Check.isin(list(GRUPO_DE_TIPO_911))),
        "fecha": pa.Column(),
        "hora": pa.Column(checks=pa.Check.in_range(0, 23)),
        "grupo_incidente": pa.Column(checks=pa.Check.isin(list(GRUPOS_INCIDENTE_911))),
        "colonia_id": pa.Column(checks=COLONIA_ID, nullable=True),
        "colonia_source": pa.Column(
            checks=pa.Check.isin(["catalogo", "equivalencia"]), nullable=True
        ),
    },
    checks=[
        pa.Check(
            lambda df: df["tipo_incidente"].map(GRUPO_DE_TIPO_911) == df["grupo_incidente"],
            name="tipo_incidente_in_its_group",
        ),
        pa.Check(
            lambda df: df["colonia_id"].isna() == df["colonia_source"].isna(),
            name="colonia_source_only_when_colonia_id",
        ),
    ],
)

PRECIPITACION_HERMOSILLO = pa.DataFrameSchema(
    {
        "date": pa.Column(unique=True),
        "precipitation_mm": pa.Column(checks=pa.Check.ge(0)),
        "precipitation_hours": pa.Column(checks=pa.Check.in_range(0, 24)),
        "month": pa.Column(checks=pa.Check.in_range(1, 12)),
        "is_rain_day": pa.Column(),
    },
    checks=[
        pa.Check(
            lambda df: df["is_rain_day"] == df["precipitation_mm"].ge(1),
            name="is_rain_day_is_1mm_or_more",
        ),
        pa.Check(lambda df: df["year"] == df["date"].dt.year, name="year_matches_date"),
    ],
)

BACHES = pa.DataFrameSchema(
    {
        # Sin rango de coordenadas: el Bachómetro trae 266 puntos fuera del municipio y
        # el procesado los conserva (ver docs/cinco_v_datos.md).
        "id": pa.Column(unique=True),
        "date": pa.Column(),
        "material": pa.Column(checks=pa.Check.isin([1, 2])),
        "year": pa.Column(checks=pa.Check.in_range(2021, datetime.now(UTC).year)),
    }
)

BACHES_CON_COLONIA = pa.DataFrameSchema(
    {
        "id": pa.Column(unique=True),
        "date": pa.Column(),
        # 0 cuando el bache no cae en ningún asentamiento ni cerca de uno.
        "colonia_id": pa.Column(checks=pa.Check.str_matches(r"^(\d{13}|0)$")),
        "colonia_source": pa.Column(
            checks=pa.Check.isin(["spatial_within", "spatial_nearest", "contexto_ubicacion"])
        ),
        "contexto_ubicacion": pa.Column(
            checks=pa.Check.isin(
                ["dentro_asentamiento", "cerca_asentamiento", "probable_carretera_o_zona_rural"]
            )
        ),
        "distance_to_colonia_m": pa.Column(checks=pa.Check.ge(0)),
    },
    checks=[
        pa.Check(
            lambda df: df["colonia_id"].eq("0") == df["colonia_source"].eq("contexto_ubicacion"),
            name="colonia_id_zero_only_without_colonia",
        ),
        pa.Check(
            lambda df: (
                df["colonia_source"].eq("spatial_within")
                == df["contexto_ubicacion"].eq("dentro_asentamiento")
            ),
            name="within_matches_contexto",
        ),
    ],
)

COLONIAS_CONTEXTO_HIDROGRAFICO = pa.DataFrameSchema(
    {
        "colonia_id": pa.Column(checks=COLONIA_ID, unique=True),
        **{f"id_seg_{k}": pa.Column(checks=pa.Check.ge(1)) for k in (1, 2, 3)},
        **{f"dist_seg_{k}": pa.Column(checks=pa.Check.ge(0)) for k in (1, 2, 3)},
        "proximity_level": pa.Column(checks=pa.Check.isin(PROXIMITY_LEVELS)),
        "context": pa.Column(checks=pa.Check.isin(list(CONTEXT_NAMES))),
        "context_name": pa.Column(checks=pa.Check.isin(list(CONTEXT_NAMES.values()))),
    },
    checks=[
        pa.Check(
            lambda df: (
                (df["dist_seg_1"] <= df["dist_seg_2"]) & (df["dist_seg_2"] <= df["dist_seg_3"])
            ),
            name="segments_sorted_by_distance",
        ),
        pa.Check(
            lambda df: df["context"].map(CONTEXT_NAMES) == df["context_name"],
            name="context_name_matches_context",
        ),
    ],
)

HL = pa.DataFrameSchema(
    {
        "geometry": pa.Column(),
        "ID": pa.Column(
            checks=pa.Check.greater_than_or_equal_to(1),
            nullable=False,
        ),
        "CVE_SUBC": pa.Column(
            pa.String,
            checks=pa.Check.str_length(6, 6),
            nullable=False,
        ),
        "CONDICION": pa.Column(
            pa.String,
            nullable=False,
        ),
        "ORDER_1": pa.Column(
            pa.Int64,
            checks=pa.Check(lambda value: (value == -1) | (value >= 1)),
            nullable=False,
        ),
        "LEVEL_1": pa.Column(
            pa.Int64,
            checks=pa.Check(lambda value: (value == -1) | (value >= 1)),
            nullable=False,
        ),
        "ARBSUM_1": pa.Column(
            checks=pa.Check.greater_than_or_equal_to(0),
            nullable=False,
        ),
        "ID_DRENA": pa.Column(
            checks=pa.Check.greater_than_or_equal_to(0),
            nullable=False,
        ),
        "ENABLED": pa.Column(
            checks=pa.Check.isin([0, 1]),
            nullable=False,
        ),
    },
    # INEGI no documenta explícitamente esta relación entre ID_DRENA y ENABLED.
    # En los datos originales de las cuatro subcuencas se observó que:
    # ENABLED=0 corresponde siempre a ID_DRENA=0, mientras que
    # ENABLED=1 corresponde a ID_DRENA>=1.
    checks=pa.Check(
        lambda df: (
            ((df["ENABLED"] == 0) & (df["ID_DRENA"] == 0))
            | ((df["ENABLED"] == 1) & (df["ID_DRENA"] >= 1))
        )
    ),
)


DR = pa.DataFrameSchema(
    {
        "geometry": pa.Column(),
        "ID": pa.Column(
            checks=pa.Check.greater_than_or_equal_to(1),
            nullable=False,
        ),
        "CVE_SUBC": pa.Column(
            pa.String,
            checks=pa.Check.str_length(6, 6),
            nullable=False,
        ),
        "CONDICION": pa.Column(
            pa.String,
            nullable=False,
        ),
        # ID_DRENA=0 aparece exclusivamente en segmentos deshabilitados (ENABLED=0),
        # y todos los segmentos deshabilitados tienen ID_DRENA=0.
        "ID_DRENA": pa.Column(
            checks=pa.Check.greater_than_or_equal_to(1),
            nullable=False,
        ),
        "ARBSUM": pa.Column(
            checks=pa.Check.greater_than_or_equal_to(0),
            nullable=False,
        ),
    }
)


SUBC = pa.DataFrameSchema(
    {
        "geometry": pa.Column(),
        "ID": pa.Column(
            checks=pa.Check.greater_than_or_equal_to(1),
            nullable=False,
        ),
        "CVE_SUBCUE": pa.Column(
            pa.String,
            checks=pa.Check.str_length(6, 6),
            nullable=False,
        ),
    }
)


HA = pa.DataFrameSchema(
    {
        "geometry": pa.Column(),
        "IDBD": pa.Column(
            pa.Int64,
            checks=pa.Check.greater_than_or_equal_to(0),
            nullable=False,
        ),
        "FC": pa.Column(
            pa.Int64,
            checks=pa.Check.greater_than_or_equal_to(0),
            nullable=False,
        ),
        "CONDICION": pa.Column(
            pa.String,
            checks=pa.Check.str_length(0, 27),
            nullable=False,
        ),
    }
)

TO = pa.DataFrameSchema(
    {
        "geometry": pa.Column(),
        "FC": pa.Column(
            pa.String,
            checks=pa.Check.str_length(0, 40),
            nullable=False,
        ),
        "CLASE": pa.Column(
            pa.String,
            checks=pa.Check.str_length(0, 60),
            nullable=False,
        ),
        "TERMINO_GE": pa.Column(
            pa.String,
            checks=pa.Check.str_length(0, 60),
            nullable=False,
        ),
        "NOMBRE": pa.Column(
            pa.String,
            checks=pa.Check.str_length(0, 120),
            nullable=False,
        ),
    }
)

# Columna extra que solo existe en el consolidado subc_hermosillo.gpkg: indica de
# cuál de las cuatro subcuencas proviene cada fila.
SUBCUENCAS = ["subc_la_manga", "subc_la_poza", "subc_r_san_miguel", "subc_r_son_hillo"]

SUBCUENCA_COL = {
    "subcuenca": pa.Column(
        pa.String,
        checks=pa.Check.isin(SUBCUENCAS),
        nullable=False,
    )
}

SCHEMAS = {
    "publicaciones_aguah": PUBLICACIONES_AGUAH,
    "colonias_hermosillo": COLONIAS_HERMOSILLO,
    "ubicaciones_aviso": UBICACIONES_AVISO,
    "llamadas_911_hermosillo": LLAMADAS_911_HERMOSILLO,
    "precipitacion_hermosillo": PRECIPITACION_HERMOSILLO,
    "baches": BACHES,
    "baches_con_colonia": BACHES_CON_COLONIA,
    "colonias_contexto_hidrografico": COLONIAS_CONTEXTO_HIDROGRAFICO,
    "subc_la_manga_hl": HL,
    "subc_la_manga_dr": DR,
    "subc_la_manga_subc": SUBC,
    "subc_la_manga_ha": HA,
    "subc_la_manga_to": TO,
    "subc_la_poza_hl": HL,
    "subc_la_poza_dr": DR,
    "subc_la_poza_subc": SUBC,
    "subc_la_poza_ha": HA,
    "subc_la_poza_to": TO,
    "subc_r_son_hillo_hl": HL,
    "subc_r_son_hillo_dr": DR,
    "subc_r_son_hillo_subc": SUBC,
    "subc_r_son_hillo_ha": HA,
    "subc_r_son_hillo_to": TO,
    "subc_r_san_miguel_hl": HL,
    "subc_r_san_miguel_dr": DR,
    "subc_r_san_miguel_subc": SUBC,
    "subc_r_san_miguel_ha": HA,
    "subc_r_san_miguel_to": TO,
    "subc_hermosillo_hl": HL.add_columns(SUBCUENCA_COL),
    "subc_hermosillo_dr": DR.add_columns(SUBCUENCA_COL),
    "subc_hermosillo_subc": SUBC.add_columns(SUBCUENCA_COL),
    "subc_hermosillo_ha": HA.add_columns(SUBCUENCA_COL),
    "subc_hermosillo_to": TO.add_columns(SUBCUENCA_COL),
    "hidrografia_cd_hermosillo_hl": HL.add_columns(SUBCUENCA_COL),
    "hidrografia_cd_hermosillo_dr": DR.add_columns(SUBCUENCA_COL),
    "hidrografia_cd_hermosillo_subc": SUBC.add_columns(SUBCUENCA_COL),
    "hidrografia_cd_hermosillo_ha": HA.add_columns(SUBCUENCA_COL),
    "hidrografia_cd_hermosillo_to": TO.add_columns(SUBCUENCA_COL),
}
