import pandas as pd

from project_name.features import GRUPOS_INCIDENTE_911, INCIDENTE_A_GRUPO_911
from project_name.jobs.process_llamadas_911_job import (
    TIPOS_INCIDENTE_EQUIVALENTES,
    unify_tipos_incidente,
)


def test_unify_tipos_incidente_maps_variants_to_the_canonical_value():
    frame = pd.DataFrame(
        {
            "tipo_incidente": [
                "INUNDACIÓN",
                "INUNDACIONES",
                "ALCANTARILLA-REGISTRO SIN TAPA",
                "SOCAVÓN",
            ]
        }
    )

    unified = unify_tipos_incidente(frame)

    assert unified["tipo_incidente"].tolist() == [
        "INUNDACIONES",
        "INUNDACIONES",
        "ALCANTARILLA SIN TAPA",
        "SOCAVÓN",
    ]
    # No modifica la tabla de entrada.
    assert frame["tipo_incidente"].iloc[0] == "INUNDACIÓN"


def test_every_variant_and_its_canonical_value_share_a_group():
    # Unificar nunca debe mover una llamada de grupo de incidente.
    for variant, canonical in TIPOS_INCIDENTE_EQUIVALENTES.items():
        assert INCIDENTE_A_GRUPO_911[variant] == INCIDENTE_A_GRUPO_911[canonical]


def test_catalog_selection_leaves_28_canonical_types():
    selected = {tipo for tipos in GRUPOS_INCIDENTE_911.values() for tipo in tipos}
    canonical = {TIPOS_INCIDENTE_EQUIVALENTES.get(tipo, tipo) for tipo in selected}

    assert len(selected) == 34
    assert len(canonical) == 28
