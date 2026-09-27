"""Reglas de calidad de los datasets procesados, una por dataset, con Pandera.

Solo viven aquí las reglas más sencillas u obvias: llaves únicas, rangos, catálogos
cerrados y coordenadas dentro de Hermosillo. `make validate` (y el final de `make data`)
las corre sobre data/processed/.
"""

from datetime import UTC, datetime

import pandera.pandas as pa

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
    )
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

SCHEMAS = {
    "publicaciones_aguah": PUBLICACIONES_AGUAH,
    "colonias_hermosillo": COLONIAS_HERMOSILLO,
    "ubicaciones_aviso": UBICACIONES_AVISO,

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
}
