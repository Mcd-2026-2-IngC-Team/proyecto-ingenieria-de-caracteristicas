"""Dibuja docs/img/volumen.svg: tamaño en disco de cada artefacto, ingesta y procesado.

Los tamaños se miden en data/ al correr el script; las etiquetas y el agrupado de
archivos están fijos abajo. Uso: uv run python scripts/figura_volumen.py
"""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
OUTPUT = ROOT / "docs" / "img" / "volumen.svg"
CUTOFF = "17 de noviembre de 2026"

# (etiqueta, patrones glob relativos a data/)
INGESTA = [
    (
        "Facebook, imágenes",
        [
            "external/facebook/images/**/*.jpg",
            "external/facebook/images/**/*.png",
            "external/facebook/images/**/*.webp",
        ],
    ),
    ("Marco Geoestadístico, capa 26e", ["raw/inegi/mg/**/*"]),
    ("Llamadas al 911 (Excel)", ["raw/llamadas911/*.xlsx"]),
    ("Red hidrográfica, 4 subcuencas", ["raw/inegi/subc_*/**/*"]),
    ("Facebook, publicaciones (CSV)", ["external/dataset_facebook-posts-scraper_*.csv"]),
    ("DCAH 2025", ["raw/inegi/dcah/**/*"]),
    ("Bachómetro", ["raw/bachometro/*.json"]),
    ("Facebook, OCR y manifiestos", ["external/facebook/**/*.csv", "external/facebook/**/*.json"]),
    ("Open-Meteo, precipitación", ["raw/precipitacion/*.json"]),
    ("Equivalencias de colonias del 911", ["external/equivalencias_colonias_911.csv"]),
]
PROCESADO = [
    (
        "subc_hermosillo.gpkg (unión)",
        ["processed/inegi/hidrografia_hermosillo/subc_hermosillo.gpkg"],
    ),
    ("subcuencas (4 GeoPackage)", ["processed/inegi/subc_*/*.gpkg"]),
    ("baches_hermosillo_filled.csv", ["processed/bachometro/baches_hermosillo_filled.csv"]),
    (
        "baches_hermosillo_con_colonias.csv",
        ["processed/bachometro/baches_hermosillo_con_colonias.csv"],
    ),
    ("baches_hermosillo.csv", ["processed/bachometro/baches_hermosillo.csv"]),
    ("publicaciones_aguah.csv", ["processed/aguah/publicaciones_aguah.csv"]),
    ("ubicaciones_aviso.csv", ["processed/aguah/ubicaciones_aviso.csv"]),
    ("colonias_hermosillo", ["processed/aguah/colonias_hermosillo.*"]),
    (
        "hidrografia_cd_hermosillo.gpkg",
        ["processed/inegi/hidrografia_hermosillo/hidrografia_cd_hermosillo.gpkg"],
    ),
    ("llamadas_911_hermosillo.csv", ["processed/llamadas_911/llamadas_911_hermosillo.csv"]),
    (
        "colonias_contexto_hidrografico.csv",
        ["processed/inegi/hidrografia_hermosillo/colonias_contexto_hidrografico.csv"],
    ),
    ("precipitacion_hermosillo.csv", ["processed/precipitacion/precipitacion_hermosillo.csv"]),
    ("relacion_colonia_baches_id.csv", ["processed/bachometro/relacion_colonia_baches_id.csv"]),
]

STYLE = """<style>
  .surface { fill: #fcfcfb; }
  .ink-1 { fill: #0b0b0b; }
  .ink-2 { fill: #52514e; }
  .axis { stroke: #c3c2b7; stroke-width: 1; fill: none; }
  .bar { fill: #2a78d6; }
  text { font-family: system-ui, -apple-system, "Segoe UI", Roboto, sans-serif; }
  .num { font-variant-numeric: tabular-nums; }
  @media (prefers-color-scheme: dark) {
    .surface { fill: #1a1a19; }
    .ink-1 { fill: #ffffff; }
    .ink-2 { fill: #c3c2b7; }
    .axis { stroke: #383835; }
    .bar { fill: #3987e5; }
  }
</style>"""

WIDTH = 760
LABEL_X = 252.0
BAR_X = 262.0
BAR_MAX = 420.0
ROW = 26
BAR_H = 16


def size_mb(patterns: list[str]) -> float:
    files = {p for pattern in patterns for p in DATA.glob(pattern) if p.is_file()}
    files = {p for p in files if p.name not in {".DS_Store", ".gitkeep"}}
    if not files:
        raise FileNotFoundError(f"Sin archivos para {patterns}")
    return sum(p.stat().st_size for p in files) / 1e6


def fmt(mb: float) -> str:
    return f"{mb:.2f} MB" if mb < 1 else f"{mb:.1f} MB"


def text(x, y, value, cls, size=12, anchor="start", weight=400):
    return (
        f'<text x="{x:.1f}" y="{y:.1f}" class="{cls}" font-size="{size}" '
        f'text-anchor="{anchor}" font-weight="{weight}">{value}</text>'
    )


def bar(y: float, width: float) -> str:
    width = max(width, 1.0)
    r = min(4.0, width / 2)
    x1 = BAR_X + width
    return (
        f'<path class="bar" d="M{BAR_X:.1f},{y:.1f} H{x1 - r:.1f} '
        f"A{r:.1f},{r:.1f} 0 0 1 {x1:.1f},{y + r:.1f} V{y + BAR_H - r:.1f} "
        f'A{r:.1f},{r:.1f} 0 0 1 {x1 - r:.1f},{y + BAR_H:.1f} H{BAR_X:.1f} Z"/>'
    )


def group(
    title: str, rows: list[tuple[str, float]], top: float, scale: float
) -> tuple[list[str], float]:
    total = sum(mb for _, mb in rows)
    parts = [text(20, top, f"{title}: {total:.1f} MB", "ink-2", weight=600)]
    y = top + 10
    for label, mb in rows:
        width = mb * scale
        parts += [
            text(LABEL_X, y + 12, label, "ink-1", anchor="end"),
            bar(y, width),
            text(BAR_X + max(width, 1.0) + 6, y + 12, fmt(mb), "ink-2 num"),
        ]
        y += ROW
    parts.append(
        f'<line class="axis" x1="{BAR_X:.0f}" y1="{top + 6:.0f}" x2="{BAR_X:.0f}" y2="{y:.0f}"/>'
    )
    return parts, y


def main() -> None:
    ingesta = [(label, size_mb(patterns)) for label, patterns in INGESTA]
    procesado = [(label, size_mb(patterns)) for label, patterns in PROCESADO]
    scale = BAR_MAX / max(mb for _, mb in ingesta + procesado)

    body, y = group("Ingesta", ingesta, 86, scale)
    more, y = group("Procesado", procesado, y + 34, scale)
    height = y + 20

    svg = [
        (
            f'<svg xmlns="http://www.w3.org/2000/svg" width="{WIDTH}" height="{height:.0f}" '
            f'viewBox="0 0 {WIDTH} {height:.0f}" role="img" aria-labelledby="t d">'
        ),
        '<title id="t">Tamaño en disco por artefacto</title>',
        (
            '<desc id="d">Barras horizontales con el tamaño en MB de cada artefacto ingerido '
            "y de cada dataset procesado.</desc>"
        ),
        STYLE,
        f'<rect class="surface" x="0" y="0" width="{WIDTH}" height="{height:.0f}" rx="8"/>',
        text(20, 30, "Tamaño en disco por artefacto", "ink-1", size=15, weight=600),
        text(
            20,
            50,
            f"Millones de bytes (MB), misma escala en ambos grupos. Corte: {CUTOFF}.",
            "ink-2",
        ),
        *body,
        *more,
        "</svg>",
    ]
    OUTPUT.write_text("\n".join(svg) + "\n", encoding="utf-8")
    for label, mb in ingesta + procesado:
        print(f"{label:40s} {mb:8.2f}")
    print(f"Escribí {OUTPUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
