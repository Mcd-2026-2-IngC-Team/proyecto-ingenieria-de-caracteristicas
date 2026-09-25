"""Reglas de texto sobre los avisos de Agua de Hermosillo: normalizar nombres, clasificar
el tipo de evento y leer la ventana de afectación que anuncia la publicación."""

import re
import unicodedata

import pandas as pd

# El participio aparece también en promesas ("el servicio empezará a ser restablecido
# alrededor de las 9:00pm"). Se borran antes de clasificar, o un aviso de cierre programado
# se cuenta como su propio cierre.
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

SPANISH_MONTHS = {
    "enero": 1, "febrero": 2, "marzo": 3, "abril": 4, "mayo": 5, "junio": 6,
    "julio": 7, "agosto": 8, "septiembre": 9, "octubre": 10, "noviembre": 11,
    "diciembre": 12,
}  # fmt: skip
SPANISH_NUMBERS = {
    "una": 1, "dos": 2, "tres": 3, "cuatro": 4, "cinco": 5, "seis": 6,
    "siete": 7, "ocho": 8, "nueve": 9, "diez": 10, "once": 11, "doce": 12,
    "dieciocho": 18, "veinticuatro": 24, "cuarenta y ocho": 48,
}  # fmt: skip

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

MAX_ANNOUNCEMENT_LEAD = pd.Timedelta(days=30)


def normalize_name(name: str) -> str:
    """Sin acentos, signos ni minúsculas: así se comparan los avisos con el INEGI."""
    decomposed = unicodedata.normalize("NFKD", str(name or ""))
    without_accents = "".join(c for c in decomposed if not unicodedata.combining(c))
    only_words = re.sub(r"[^A-Z0-9 ]", " ", without_accents.upper())
    return re.sub(r"\s+", " ", only_words).strip()


def classify_events(haystack: pd.Series) -> pd.Series:
    """Tipo de evento por reglas, en orden de prioridad: gana la última asignación."""
    haystack = haystack.str.replace(FUTURE_RESTORE, " ", regex=True)
    event_type = pd.Series("otro", index=haystack.index, dtype="object")
    event_type[haystack.str.contains(TRUCKS, regex=True)] = "pipas"
    event_type[haystack.str.contains(EMERGENCY, regex=True)] = "emergencia"
    event_type[haystack.str.contains(SCHEDULED, regex=True)] = "corte_programado"
    event_type[haystack.str.contains(RESTORED, regex=True)] = "restablecimiento"
    return event_type


def parse_duration_hours(text: str) -> float | None:
    for found in DURATION_PATTERN.finditer(text):
        # "las 24 horas" es el teléfono de atención, no la duración de un corte.
        if text[max(0, found.start() - 4) : found.start()].strip().endswith("las"):
            continue
        value = found.group(1)
        return float(value) if value.isdigit() else float(SPANISH_NUMBERS[value])
    return None


def parse_start(text: str, published_at: pd.Timestamp) -> pd.Timestamp | None:
    """Inicio anunciado. El aviso no escribe el año, así que se toma el de la publicación."""
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

    candidates = []
    for year in (published_at.year - 1, published_at.year, published_at.year + 1):
        try:
            candidates.append(pd.Timestamp(year, month, day, hour, minute))
        except ValueError:
            continue
    if not candidates:
        return None
    closest = min(candidates, key=lambda stamp: abs(stamp - published_at))
    return closest if abs(closest - published_at) <= MAX_ANNOUNCEMENT_LEAD else None
