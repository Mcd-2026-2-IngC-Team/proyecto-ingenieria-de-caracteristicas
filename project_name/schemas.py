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

# Claves que el CSV guardaría como número, perdiendo los ceros a la izquierda.
READ_DTYPES = {
    "colonias_hermosillo": {"colonia_id": str, "locality_code": str, "postal_code": str},
    "ubicaciones_aviso": {"colonia_id": str},
}

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
    checks=pa.Check(
        lambda df: df["reactions_total"] == df[[f"reactions_{n}" for n in REACTIONS]].sum(axis=1),
        name="reactions_total_is_sum_of_reactions",
    ),
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
    }
)

SCHEMAS = {
    "publicaciones_aguah": PUBLICACIONES_AGUAH,
    "colonias_hermosillo": COLONIAS_HERMOSILLO,
    "ubicaciones_aviso": UBICACIONES_AVISO,
}
