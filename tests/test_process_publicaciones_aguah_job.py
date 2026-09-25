import pandas as pd

from project_name.jobs.process_publicaciones_aguah_job import (
    build_publicaciones,
    build_reactions,
    build_time_features,
)


def make_posts(**overrides) -> pd.DataFrame:
    row = {
        "postId": 1,
        # Mediodía UTC es media mañana en Hermosillo: la conversión tiene que notarse.
        "time": "2024-08-15T19:30:00.000Z",
        "text": "Atendemos una fuga en la colonia Centro",
        "likes": 10.0,
        "comments": 4.0,
        "shares": 2.0,
        "reactionLikeCount": 5.0,
        "reactionLoveCount": None,
        "reactionHahaCount": None,
        "reactionWowCount": None,
        "reactionSadCount": None,
        "reactionAngryCount": 15.0,
        "reactionCareCount": None,
        "topComments/0/text": "otra vez sin agua",
        "topComments/0/likesCount": 3.0,
        "media/0/photo_image/uri": "https://example.com/a.jpg",
        "source_slug": "2024-04-07-to-2024-12-31",
        "ocr_text": None,
        "ocr_status": "skipped_no_image",
    }
    row.update(overrides)
    return pd.DataFrame([row])


def test_build_time_features_converts_to_hermosillo_time():
    # Sonora no aplica horario de verano: siempre UTC-7, incluso en agosto.
    features = build_time_features(make_posts())

    assert features.loc[0, "published_at"] == pd.Timestamp("2024-08-15 12:30")
    assert features.loc[0, "hour_of_day"] == 12
    assert features.loc[0, "day_of_week"] == 3


def test_build_reactions_treats_missing_reactions_as_zero():
    """Las columnas vienen vacías, no en cero, cuando nadie reaccionó así."""
    reactions = build_reactions(make_posts())

    assert reactions.loc[0, "reactions_love"] == 0
    assert reactions.loc[0, "reactions_total"] == 20
    assert reactions.loc[0, "angry_share"] == 0.75


def test_build_reactions_leaves_the_share_null_without_reactions():
    # Sin reacciones no hay proporción que reportar: un 0 inventaría una lectura.
    silent = make_posts(reactionLikeCount=None, reactionAngryCount=None)

    reactions = build_reactions(silent)

    assert reactions.loc[0, "reactions_total"] == 0
    assert pd.isna(reactions.loc[0, "angry_share"])


def test_build_publicaciones_drops_the_commenter_name():
    tidy = build_publicaciones(make_posts())

    assert "top_comment_text" in tidy.columns
    assert not [column for column in tidy.columns if "profile" in column.lower()]


def test_build_publicaciones_reads_the_announced_window():
    notice = make_posts(
        text="El 21 de enero a partir de las 9:00am habrá un corte programado de 5 horas",
        time="2022-01-18T17:00:00.000Z",
    )

    tidy = build_publicaciones(notice)

    assert tidy.loc[0, "event_type"] == "corte_programado"
    assert tidy.loc[0, "announced_duration_hours"] == 5.0
    assert tidy.loc[0, "announced_start_at"] == pd.Timestamp("2022-01-21 09:00")


def test_build_publicaciones_classifies_with_the_ocr_text():
    """El volante trae información que el cuerpo de la publicación no menciona."""
    silent_body = make_posts(text="AGUA DE HERMOSILLO INFORMA", ocr_text="CORTE PROGRAMADO")

    tidy = build_publicaciones(silent_body)

    assert tidy.loc[0, "event_type"] == "corte_programado"
