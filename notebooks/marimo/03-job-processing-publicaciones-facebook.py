import marimo

__generated_with = "0.24.0"
app = marimo.App(width="medium")


@app.cell
def _():
    import marimo as mo

    return (mo,)


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    # Publicaciones de Agua de Hermosillo (Facebook + OCR)

    Este notebook construye una tabla tidy con una fila por
    publicación de la página oficial de Agua de Hermosillo. Sobre ella se apoyan las demás
    vistas para medir vive a nivel publicación: cuándo se
    anuncian las afectaciones, cuánta molestia generan y de qué tipo son.

    ## Objetivos del experimento
    1. Consolidar los 7 CSVs del scraper en una sola tabla, con una lista explícita de columnas.
    2. Unir el texto extraído por OCR de los volantes (unión 1:1 por `postId`).
    3. Pasar la marca de tiempo a hora local de Hermosillo y derivar atributos de calendario.
    4. Construir la señal de molestia ciudadana a partir de las reacciones de enojo.
    5. Clasificar el tipo de evento con reglas sobre el texto, y medir cuánto aporta el OCR.
    6. Extraer la ventana de afectación anunciada cuando la publicación la declara.
    7. Guardar el resultado en `data/processed/` sin datos personales.
    """)
    return


@app.cell
def _():
    from pathlib import Path
    import re
    import unicodedata

    import pandas as pd

    from project_name.config import load_dataset_config, load_params

    return Path, load_dataset_config, load_params, pd, re


@app.cell
def _(Path, load_dataset_config, load_params):
    params = load_params()
    dataset = load_dataset_config(params, source="agua_hermosillo", dataset="publicaciones_aguah")

    external = dataset["external"]
    posts_files = sorted(Path(external["posts_directory"]).glob(external["posts_pattern"]))
    ocr_files = sorted(Path(external["ocr_directory"]).glob(external["ocr_pattern"]))

    processed_dir = Path(dataset["processed"]["directory"])
    processed_file = processed_dir / dataset["processed"]["filename"]

    len(posts_files), len(ocr_files)
    return ocr_files, posts_files, processed_dir, processed_file


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## Consolidar los 7 exports del scraper

    El scraper entrega un CSV por rango de fechas y el número de columnas varía mucho entre
    ellos (de 936 a 2000): aplana los objetos anidados de Facebook en columnas como
    `topComments/0/text`, y cuántas genera depende de lo que traiga cada lote. Por eso
    pedimos una lista explícita de columnas en vez de concatenar a ciegas; así el
    esquema no depende del lote que nos haya tocado.

    Nos quedamos con `time` (ISO 8601 en UTC) y descartamos `timestamp` (Unix), que es la
    misma información. Guardamos también de qué export salió cada fila (`source_slug`),
    porque `postId` solo es único dentro de un archivo.
    """)
    return


@app.cell
def _(pd, posts_files):
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

    posts_raw = pd.concat(
        [
            pd.read_csv(file, usecols=POST_COLUMNS).assign(
                source_slug=file.stem.replace("dataset_facebook-posts-scraper_", "")
            )
            for file in posts_files
        ],
        ignore_index=True,
    )

    assert len(posts_raw) == 5200, f"Se esperaban 5,200 publicaciones, hay {len(posts_raw)}"
    assert posts_raw["postId"].is_unique, "postId se repite entre exports"
    posts_raw.shape
    return (posts_raw,)


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## Unir el texto del OCR

    Los volantes de Agua de Hermosillo traen fechas, horarios y tablas de colonias que no
    aparecen en el cuerpo de la publicación; recuperar eso fue el motivo de correr
    PaddleOCR-VL sobre las imágenes. El OCR entrega un CSV por export, con una fila por
    publicación, así que la unión es 1:1 por `postId` y la validamos como tal.

    Ojo con una trampa: el scraper trae una columna `media/0/ocrText` que no es OCR, es
    el texto alternativo de Facebook y suele decir literalmente *"No photo description
    available."*. El OCR bueno es el de estos archivos.
    """)
    return


@app.cell
def _(ocr_files, pd, posts_raw):
    ocr_raw = pd.concat([pd.read_csv(file) for file in ocr_files], ignore_index=True)
    ocr_raw = ocr_raw.rename(columns={"id": "postId", "text": "ocr_text", "status": "ocr_status"})

    posts = posts_raw.merge(
        ocr_raw[["postId", "ocr_text", "ocr_status"]],
        on="postId",
        how="left",
        validate="1:1",
    )

    assert len(posts) == len(posts_raw), "La unión con el OCR duplicó o perdió filas"
    posts["ocr_status"].value_counts(dropna=False)
    return (posts,)


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## Tiempo: a hora de Hermosillo

    El scraper entrega la hora en UTC y la pregunta del tablero es sobre el ritmo: en qué
    semanas se concentran las afectaciones y a qué hora del día se avisa. Hay que leerla en
    hora local o los cortes de día y de semana quedan corridos.

    Sonora no aplica horario de verano, así que la conversión es un desplazamiento fijo
    de UTC-7 todo el año. Eso nos ahorra la ambigüedad de las horas repetidas.
    """)
    return


@app.cell
def _(pd, posts):
    HERMOSILLO_TZ = "America/Hermosillo"

    published_at = pd.to_datetime(posts["time"], utc=True).dt.tz_convert(HERMOSILLO_TZ)

    time_features = pd.DataFrame(
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

    time_features["published_at"].agg(["min", "max"])
    return (time_features,)


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## Molestia ciudadana: las reacciones de enojo

    No tenemos los comentarios completos (serían ~95,671 y su scraping no es viable), así
    que la molestia se aproxima con dos señales que sí están: el enojo por publicación y
    qué proporción del total de reacciones es enojo. La segunda importa porque una
    publicación muy vista acumula más de todo; la proporción corrige por alcance.

    Una trampa verificada: las columnas de reacción vienen vacías, no en cero, cuando
    nadie reaccionó así. Si no las llenamos con 0, cualquier promedio de enojo se calcula
    sobre un subconjunto y sale inflado.

    Tampoco usamos `topReactionsCount`: no es un total, es cuántos tipos distintos de
    reacción muestra Facebook.
    """)
    return


@app.cell
def _(pd, posts):
    REACTION_COLUMNS = {
        "reactionLikeCount": "reactions_like",
        "reactionLoveCount": "reactions_love",
        "reactionHahaCount": "reactions_haha",
        "reactionWowCount": "reactions_wow",
        "reactionSadCount": "reactions_sad",
        "reactionAngryCount": "reactions_angry",
        "reactionCareCount": "reactions_care",
    }

    reactions = posts[list(REACTION_COLUMNS)].rename(columns=REACTION_COLUMNS).fillna(0)
    reactions = reactions.astype("int64")
    reactions["reactions_total"] = reactions.sum(axis=1)

    # Sin reacciones no hay proporción que reportar: dejarlo en 0 inventaría una lectura.
    reactions["angry_share"] = (
        reactions["reactions_angry"] / reactions["reactions_total"].replace(0, pd.NA)
    ).astype("Float64")

    engagement = pd.DataFrame(
        {
            "comments_count": posts["comments"].fillna(0).astype("int64"),
            "shares_count": posts["shares"].fillna(0).astype("int64"),
            "likes_count": posts["likes"].fillna(0).astype("int64"),
        }
    )

    reactions[["reactions_angry", "reactions_total", "angry_share"]].describe()
    return engagement, reactions


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## Tipo de evento

    Clasificamos con reglas sobre el texto, no con un modelo.

    Las reglas se aplican en orden de prioridad y gana la primera, porque una misma
    publicación menciona varias cosas: un aviso de restablecimiento casi siempre nombra la
    fuga que lo originó.

    | Orden | Tipo | Se reconoce por |
    |---|---|---|
    | 1 | `restablecimiento` | obra terminada: "restablecido", "se restableció", "se normalizó", "reanudó", "concluyó la reparación" |
    | 2 | `corte_programado` | "programado", "suspensión del servicio" |
    | 3 | `emergencia` | "fuga", "ruptura", "emergencia", "falla eléctrica", "desabasto" |
    | 4 | `pipas` | "pipa" |
    | 5 | `otro` | lo demás: campañas, pagos, comunicados institucionales |

    La distinción entre "restablecer" (infinitivo o futuro) y "restablecido" o "concluyó la
    reparación" (obra terminada) aparece en avisos de
    trabajos en curso ("personal técnico atiende la eventualidad para restablecer
    servicio"), que son la emergencia misma y no su cierre. Hay 128 publicaciones que solo
    dicen "restablecer" o "se restablecerá": contarlas como cierres inflaría el número de
    eventos resueltos: un aviso de trabajos en curso se contaría como si el servicio ya
    hubiera vuelto.
    """)
    return


@app.cell
def _(pd, posts):
    # El participio también aparece en promesas ("el servicio empezará a ser restablecido
    # alrededor de las 9:00pm"). Borramos esas construcciones antes de clasificar, o un
    # aviso de cierre programado se contaría como su propio cierre.
    FUTURE_RESTORE = (
        r"(?:ser[aá]n?|ser|quedar[aá]n?|estar[aá]n?|empezar[aá]n?\s+a\s+ser)\s+restablecid\w*"
        r"|se\s+restablecer[aá]n?"
    )
    RESTORED = (
        r"restablecid[oa]|se restableci[oó]|qued[oó]\s+restablecid|se normaliz[oó]|"
        r"reanud[oó]|concluy\w+\s+(?:la\s+|los\s+|el\s+)?(?:reparaci|trabajo|maniobra)|"
        r"ya cuenta con (?:el )?servicio"
    )
    SCHEDULED = r"programad|suspensi[oó]n del servicio|corte del servicio"
    EMERGENCY = r"fuga|ruptura|emergencia|falla el[eé]ctrica|desabasto"
    TRUCKS = r"pipa"

    def classify_events(haystack: pd.Series) -> pd.Series:
        haystack = haystack.str.replace(FUTURE_RESTORE, " ", regex=True)
        event_type = pd.Series("otro", index=haystack.index, dtype="object")
        # De menor a mayor prioridad: la última asignación es la que queda.
        event_type[haystack.str.contains(TRUCKS, regex=True)] = "pipas"
        event_type[haystack.str.contains(EMERGENCY, regex=True)] = "emergencia"
        event_type[haystack.str.contains(SCHEDULED, regex=True)] = "corte_programado"
        event_type[haystack.str.contains(RESTORED, regex=True)] = "restablecimiento"
        return event_type

    post_text = posts["text"].fillna("").str.lower()
    ocr_text = posts["ocr_text"].fillna("").str.lower()

    event_type_post_only = classify_events(post_text)
    event_type = classify_events(post_text + " \n " + ocr_text)
    return event_type, event_type_post_only, ocr_text, post_text


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ### Cuánto aporta el OCR

    Comparamos la clasificación usando solo el cuerpo de la publicación contra la que usa
    también el texto del volante. La diferencia es el argumento a favor de haber corrido el
    OCR: si el volante no aportara nada, ambas columnas serían iguales.
    """)
    return


@app.cell
def _(event_type, event_type_post_only, pd):
    coverage = pd.DataFrame(
        {
            "solo_publicacion": event_type_post_only.value_counts(),
            "publicacion_y_ocr": event_type.value_counts(),
        }
    ).fillna(0).astype("int64")
    coverage.loc["TOTAL clasificadas"] = [
        (event_type_post_only != "otro").sum(),
        (event_type != "otro").sum(),
    ]
    coverage
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## Ventana de afectación anunciada

    Para preguntar cuánto duran realmente frente a lo que se anuncia, primero hay que leer
    lo anunciado. Dos piezas, y cada una con su propia cobertura:

    - Duración: frases como "corte programado de siete horas". Aceptamos el número en
      dígitos y en palabra, porque los avisos usan ambos.
    - Inicio: la fecha que nombra el aviso ("este próximo viernes 21 de enero") más la
      hora de arranque (*"a partir de las 9:00am"*). El año casi nunca se escribe, así que lo
      tomamos del año de publicación y verificamos que la fecha caiga cerca: si queda a más de
      30 días, la descartamos en vez de inventar un año.

    Lo que no se pueda extraer queda nulo. La cobertura de estas dos columnas es un
    resultado del análisis, porque dice qué tan explícita es la comunicación de la
    dependencia, así que la reportamos en vez de rellenarla.
    """)
    return


@app.cell
def _(pd, re):
    SPANISH_MONTHS = {
        "enero": 1,
        "febrero": 2,
        "marzo": 3,
        "abril": 4,
        "mayo": 5,
        "junio": 6,
        "julio": 7,
        "agosto": 8,
        "septiembre": 9,
        "octubre": 10,
        "noviembre": 11,
        "diciembre": 12,
    }
    SPANISH_NUMBERS = {
        "una": 1, "dos": 2, "tres": 3, "cuatro": 4, "cinco": 5, "seis": 6,
        "siete": 7, "ocho": 8, "nueve": 9, "diez": 10, "once": 11, "doce": 12,
        "dieciocho": 18, "veinticuatro": 24, "cuarenta y ocho": 48,
    }

    # Las alternativas largas van primero o "cuarenta y ocho" se quedaría en "ocho".
    NUMBER_WORDS = "|".join(sorted(SPANISH_NUMBERS, key=len, reverse=True))
    DURATION_PATTERN = re.compile(
        r"(?:de|por|durante|en|dura(?:r[aá]|ci[oó]n de)|no mayor a|estima(?:do|n)? en"
        r"|aproximadamente)\s+(\d{1,3}|" + NUMBER_WORDS + r")\s*horas"
    )
    DATE_PATTERN = re.compile(r"(\d{1,2})\s+de\s+(" + "|".join(SPANISH_MONTHS) + r")")
    START_TIME_PATTERN = re.compile(
        r"(?:a partir de las?|de las?|inicio a las?)\s*(\d{1,2})(?::(\d{2}))?\s*(am|pm|hrs|horas)?"
    )

    def parse_duration_hours(text: str) -> float | None:
        for found in DURATION_PATTERN.finditer(text):
            # "las 24 horas" es el teléfono de atención, no la duración de un corte.
            if text[max(0, found.start() - 4) : found.start()].strip().endswith("las"):
                continue
            value = found.group(1)
            return float(value) if value.isdigit() else float(SPANISH_NUMBERS[value])
        return None

    def parse_start(text: str, published_at: pd.Timestamp) -> pd.Timestamp | None:
        date_found = DATE_PATTERN.search(text)
        if not date_found or pd.isna(published_at):
            return None
        day, month = int(date_found.group(1)), SPANISH_MONTHS[date_found.group(2)]

        hour, minute = 0, 0
        time_found = START_TIME_PATTERN.search(text)
        if time_found:
            hour = int(time_found.group(1))
            minute = int(time_found.group(2) or 0)
            if time_found.group(3) == "pm" and hour < 12:
                hour += 12

        # El aviso no escribe el año; probamos el de la publicación y sus vecinos, y nos
        # quedamos con el que caiga más cerca de la fecha en que se publicó.
        candidates = []
        for year in (published_at.year - 1, published_at.year, published_at.year + 1):
            try:
                candidates.append(pd.Timestamp(year, month, day, hour, minute))
            except ValueError:
                continue
        if not candidates:
            return None
        closest = min(candidates, key=lambda stamp: abs(stamp - published_at))
        return closest if abs(closest - published_at) <= pd.Timedelta(days=30) else None

    return parse_duration_hours, parse_start


@app.cell
def _(
    ocr_text,
    parse_duration_hours,
    parse_start,
    pd,
    post_text,
    time_features,
):
    announcement_text = post_text + " \n " + ocr_text

    announced_duration_hours = announcement_text.map(parse_duration_hours)
    announced_start_at = pd.Series(
        [
            parse_start(text, stamp)
            for text, stamp in zip(announcement_text, time_features["published_at"])
        ],
        index=announcement_text.index,
    )
    pd.DataFrame(
        {
            "columna": ["announced_duration_hours", "announced_start_at"],
            "con_valor": [
                announced_duration_hours.notna().sum(),
                announced_start_at.notna().sum(),
            ],
            "cobertura": [
                f"{announced_duration_hours.notna().mean():.1%}",
                f"{announced_start_at.notna().mean():.1%}",
            ],
        }
    )
    return announced_duration_hours, announced_start_at


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## Armar la tabla tidy

    Una fila por publicación y una variable por columna. Dejamos fuera el nombre de quien
    comentó: es una persona identificable y el tablero no necesita saber quién escribió para
    medir molestia. Conservamos el texto del comentario y sus likes.
    """)
    return


@app.cell
def _(
    announced_duration_hours,
    announced_start_at,
    engagement,
    event_type,
    pd,
    posts,
    reactions,
    time_features,
):
    tidy = pd.concat(
        [
            pd.DataFrame(
                {
                    "post_id": posts["postId"],
                    "source_slug": posts["source_slug"],
                }
            ),
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
            engagement,
            pd.DataFrame(
                {
                    "top_comment_text": posts["topComments/0/text"],
                    "top_comment_likes": posts["topComments/0/likesCount"].fillna(0).astype("int64"),
                    "event_type": event_type,
                    "announced_start_at": announced_start_at,
                    "announced_duration_hours": announced_duration_hours,
                }
            ),
        ],
        axis=1,
    )

    assert len(tidy) == 5200, f"Se esperaban 5,200 filas, hay {len(tidy)}"
    assert tidy["post_id"].is_unique, "post_id no es llave"
    assert not tidy.columns.duplicated().any(), "Hay columnas repetidas"
    tidy.head()
    return (tidy,)


@app.cell
def _(tidy):
    has_announcement = tidy["announced_duration_hours"].notnull()
    tidy[["text", "announced_duration_hours", "announced_start_at"]][has_announcement]
    return


@app.cell
def _(processed_dir, processed_file, tidy):
    processed_dir.mkdir(parents=True, exist_ok=True)
    tidy.to_csv(processed_file, index=False)
    print(f"Guardadas {len(tidy)} publicaciones ({len(tidy.columns)} columnas) -> {processed_file}")
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## Hallazgos y siguientes pasos

    - Solo una de cada cuatro publicaciones anuncia una afectación. El resto son campañas,
      avisos de pago y comunicados institucionales, así que el tablero se construye sobre una
      porción chica de lo que publica la dependencia.
    - Sumar el texto del volante sube los cortes programados de 207 a 288.
      Son 81 avisos donde la dependencia puso la información solo en la imagen y que, sin OCR,
      habrían quedado invisibles para el tablero.
    - El enojo promedio por publicación pasa de 2.5 en
      enero a 14.5 en agosto, y 2024 es el año más cargado con 10,235 enojos. El verano es el
      periodo crítico.
    - Los `restablecimiento` son pocos, 134 frente a 1,106 avisos de afectación. Aquí solo
      cuenta la obra terminada, no la promesa, y aun así la conclusión no cambiaría mucho
      siendo más laxos: la dependencia simplemente no publica el cierre de cada aviso. Esa
      asimetría, avisar mucho más la falla que la solución, es un resultado sobre cómo
      comunica el organismo y a la vez la razón de que no se pueda medir cuánto duran
      realmente las afectaciones con esta fuente.
    - El participio también aparece en
      promesas ("el servicio empezará a ser restablecido alrededor de las 9:00pm"). Son
      46 publicaciones, y en 12 de ellas esa promesa era la única señal de cierre. Sin
      descartarlas, un aviso de cierre programado se contaba como su propio cierre y la
      duración real habría salido de cero horas.
    - La ventana anunciada es escasa y desbalanceada: 10.7% de las publicaciones declaran
      una duración y 30.0% una fecha de inicio, pero solo 1.7% declaran ambas. La frase más
      común es "de no presentarse inconvenientes, en 4 horas", que promete un plazo sin
      fijar una fecha. Eso ya es un hallazgo sobre cómo comunica la dependencia: promete
      plazos sin comprometerse con un momento concreto.
    - Sobre la duración real: se intentó emparejar cada aviso con su publicación de cierre
      para medirla, y no alcanza. Solo 17 de 1,106 avisos admiten un cierre defendible y
      apenas 4 declaran además una duración, así que la comparación "anunciado contra real"
      no da para sostener una vista del tablero. Lo que sí es descriptivo y tiene cobertura
      es la duración anunciada, que ya vive en este dataset.
    - Siguiente: `04-job-processing-ubicaciones-colonias`, que resuelve dónde pega cada
      aviso. Después, convertir este notebook en un job (`process_publicaciones_aguah_job`).
    """)
    return


if __name__ == "__main__":
    app.run()
