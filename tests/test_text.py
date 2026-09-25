import pandas as pd

from project_name.text import (
    classify_events,
    normalize_name,
    parse_duration_hours,
    parse_start,
)


def classify_one(text: str) -> str:
    return classify_events(pd.Series([text.lower()])).iloc[0]


def test_normalize_name_strips_accents_punctuation_and_case():
    assert normalize_name("Misión del Arco") == "MISION DEL ARCO"
    assert normalize_name("  H. Ayuntamiento  ") == "H AYUNTAMIENTO"


def test_classify_events_applies_priority_order():
    # Un cierre casi siempre nombra la fuga que lo originó: gana el cierre.
    assert classify_one("concluyó la reparación de la fuga en Obregón") == "restablecimiento"
    assert classify_one("corte programado por trabajos de interconexión") == "corte_programado"
    assert classify_one("atendemos una fuga en la colonia Centro") == "emergencia"
    assert classify_one("se envían pipas a la zona") == "pipas"
    assert classify_one("jornada de descuentos en tu recibo") == "otro"


def test_classify_events_ignores_promises_of_restoration():
    """El participio en futuro es una promesa, no una obra terminada.

    Sin esta regla un aviso de corte programado se contaba como su propio cierre.
    """
    assert (
        classify_one(
            "se realizará un cierre programado; el servicio empezará a ser restablecido "
            "alrededor de las 9:00pm"
        )
        == "corte_programado"
    )
    assert classify_one("personal técnico trabaja para restablecer servicio") != "restablecimiento"
    assert classify_one("el servicio se restablecerá este mismo día") != "restablecimiento"


def test_parse_duration_hours_reads_digits_and_words():
    assert parse_duration_hours("corte programado de siete horas") == 7.0
    assert parse_duration_hours("de no presentarse inconvenientes, en 4 horas") == 4.0
    assert parse_duration_hours("los trabajos concluyen en cuarenta y ocho horas") == 48.0


def test_parse_duration_hours_ignores_the_service_phone():
    # "las 24 horas" es el teléfono de atención, no la duración de un corte.
    assert parse_duration_hours("reporta tu fuga las 24 horas") is None
    assert parse_duration_hours("un aviso sin plazo declarado") is None


def test_parse_start_takes_the_year_from_the_publication():
    published = pd.Timestamp("2022-01-18 10:00")
    assert parse_start("este viernes 21 de enero a partir de las 9:00am", published) == (
        pd.Timestamp("2022-01-21 09:00")
    )


def test_parse_start_reads_the_afternoon():
    published = pd.Timestamp("2022-01-18 10:00")
    assert parse_start("el 21 de enero a partir de las 5:00pm", published) == (
        pd.Timestamp("2022-01-21 17:00")
    )


def test_parse_start_crosses_the_new_year():
    # Publicado en diciembre, el aviso nombra enero: es del año siguiente, no del mismo.
    published = pd.Timestamp("2021-12-28 10:00")
    assert parse_start("el 3 de enero", published) == pd.Timestamp("2022-01-03 00:00")


def test_parse_start_discards_dates_far_from_the_publication():
    # A más de 30 días no se puede saber de qué año habla, así que no se inventa.
    published = pd.Timestamp("2022-01-18 10:00")
    assert parse_start("el 15 de agosto", published) is None
    assert parse_start("un aviso sin fecha", published) is None
