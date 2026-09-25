from pathlib import Path

from loguru import logger
import pandas as pd

from project_name.config import load_dataset_config, load_logging, load_params
from project_name.logging import log_execution
from project_name.text import classify_events, parse_duration_hours, parse_start

# Sonora no aplica horario de verano: la conversión es un desplazamiento fijo todo el año.
HERMOSILLO_TZ = "America/Hermosillo"

# El scraper aplana los objetos de Facebook y entrega entre 936 y 2000 columnas según el
# lote, así que se piden explícitamente en vez de concatenar a ciegas.
POST_COLUMNS = [
    "postId",
    "time",
    "text",
    "likes",
    "comments",
    "shares",
    "reactionLikeCount",
    "reactionLoveCount",
    "reactionHahaCount",
    "reactionWowCount",
    "reactionSadCount",
    "reactionAngryCount",
    "reactionCareCount",
    "topComments/0/text",
    "topComments/0/likesCount",
    "media/0/photo_image/uri",
]
REACTION_COLUMNS = {
    "reactionLikeCount": "reactions_like",
    "reactionLoveCount": "reactions_love",
    "reactionHahaCount": "reactions_haha",
    "reactionWowCount": "reactions_wow",
    "reactionSadCount": "reactions_sad",
    "reactionAngryCount": "reactions_angry",
    "reactionCareCount": "reactions_care",
}


def read_posts(files: list[Path]) -> pd.DataFrame:
    posts = pd.concat(
        [
            pd.read_csv(file, usecols=POST_COLUMNS).assign(
                source_slug=file.stem.replace("dataset_facebook-posts-scraper_", "")
            )
            for file in files
        ],
        ignore_index=True,
    )
    if not posts["postId"].is_unique:
        raise ValueError("postId se repite entre los exports del scraper")
    return posts


def read_ocr(files: list[Path]) -> pd.DataFrame:
    ocr = pd.concat([pd.read_csv(file) for file in files], ignore_index=True)
    ocr = ocr.rename(columns={"id": "postId", "text": "ocr_text", "status": "ocr_status"})
    return ocr[["postId", "ocr_text", "ocr_status"]]


def build_time_features(posts: pd.DataFrame) -> pd.DataFrame:
    published_at = pd.to_datetime(posts["time"], utc=True).dt.tz_convert(HERMOSILLO_TZ)
    return pd.DataFrame(
        {
            # Sin zona horaria: ya está en hora local y así viaja limpia al CSV.
            "published_at": published_at.dt.tz_localize(None),
            "year": published_at.dt.year,
            "month": published_at.dt.month,
            "iso_week": published_at.dt.isocalendar().week.astype("int64"),
            "day_of_week": published_at.dt.dayofweek,
            "hour_of_day": published_at.dt.hour,
        }
    )


def build_reactions(posts: pd.DataFrame) -> pd.DataFrame:
    # Las columnas de reacción vienen vacías, no en cero, cuando nadie reaccionó así.
    reactions = posts[list(REACTION_COLUMNS)].rename(columns=REACTION_COLUMNS).fillna(0)
    reactions = reactions.astype("int64")
    reactions["reactions_total"] = reactions.sum(axis=1)
    # Sin reacciones no hay proporción que reportar: dejarlo en 0 inventaría una lectura.
    reactions["angry_share"] = (
        reactions["reactions_angry"] / reactions["reactions_total"].replace(0, pd.NA)
    ).astype("Float64")
    return reactions


def build_publicaciones(posts: pd.DataFrame) -> pd.DataFrame:
    """De publicaciones crudas más OCR a la tabla tidy, una fila por publicación."""
    time_features = build_time_features(posts)
    reactions = build_reactions(posts)

    post_text = posts["text"].fillna("").str.lower()
    ocr_text = posts["ocr_text"].fillna("").str.lower()
    announcement = post_text + " \n " + ocr_text

    announced_duration_hours = announcement.map(parse_duration_hours)
    announced_start_at = pd.Series(
        [
            parse_start(text, stamp)
            for text, stamp in zip(announcement, time_features["published_at"])
        ],
        index=announcement.index,
    )

    return pd.concat(
        [
            pd.DataFrame({"post_id": posts["postId"], "source_slug": posts["source_slug"]}),
            time_features,
            pd.DataFrame(
                {
                    "text": posts["text"],
                    "has_text": posts["text"].notna(),
                    "ocr_text": posts["ocr_text"],
                    "ocr_status": posts["ocr_status"],
                    "has_image": posts["media/0/photo_image/uri"].notna(),
                }
            ),
            reactions,
            pd.DataFrame(
                {
                    "comments_count": posts["comments"].fillna(0).astype("int64"),
                    "shares_count": posts["shares"].fillna(0).astype("int64"),
                    "likes_count": posts["likes"].fillna(0).astype("int64"),
                }
            ),
            pd.DataFrame(
                {
                    # Sin el nombre de quien comentó: es una persona identificable y el
                    # tablero no lo necesita para medir molestia.
                    "top_comment_text": posts["topComments/0/text"],
                    "top_comment_likes": posts["topComments/0/likesCount"]
                    .fillna(0)
                    .astype("int64"),
                    "event_type": classify_events(announcement),
                    "announced_start_at": announced_start_at,
                    "announced_duration_hours": announced_duration_hours,
                }
            ),
        ],
        axis=1,
    )


@log_execution
def process_publicaciones_aguah(params: dict) -> None:
    dataset = load_dataset_config(params, source="agua_hermosillo", dataset="publicaciones_aguah")
    external = dataset["external"]

    posts_files = sorted(Path(external["posts_directory"]).glob(external["posts_pattern"]))
    ocr_files = sorted(Path(external["ocr_directory"]).glob(external["ocr_pattern"]))
    logger.info("Reading {} post exports and {} OCR exports", len(posts_files), len(ocr_files))

    posts = read_posts(posts_files)
    ocr = read_ocr(ocr_files)
    posts = posts.merge(ocr, on="postId", how="left", validate="1:1")
    logger.info("Read {} publications", len(posts))

    tidy = build_publicaciones(posts)

    processed_dir = Path(dataset["processed"]["directory"])
    processed_dir.mkdir(parents=True, exist_ok=True)
    processed_file = processed_dir / dataset["processed"]["filename"]
    tidy.to_csv(processed_file, index=False)
    logger.info("Wrote processed data → {}", processed_file)


if __name__ == "__main__":
    params = load_params()

    load_logging(
        level=params["logging"]["level"],
        log_file=Path(params["logging"]["file"]),
        console=params["logging"].get("console", False),
    )

    process_publicaciones_aguah(params)
