"""Utilidades compartidas por los notebooks de análisis exploratorio.

Los notebooks `notebooks/marimo/05` a `07` hacen el mismo recorrido sobre cada dataset
tidy (auto EDA, faltantes, anomalías, relaciones, correlación y reducción a 2D); aquí vive
lo que se repite para que cada notebook lea como análisis y no como plomería.
"""

import json
from pathlib import Path
import re
import subprocess
import warnings

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from pyod.models.ecod import ECOD
from pyod.models.iforest import IForest
from pyod.models.lof import LOF
from scipy.stats import chi2_contingency
from sklearn.decomposition import PCA
from sklearn.manifold import TSNE, trustworthiness
import umap

from project_name.config import PROJECT_ROOT, load_dataset_config, load_params

RANDOM_STATE = 42

# Paleta categórica de referencia (skill dataviz), en orden fijo; en scatter solo se
# usan las tres primeras y el resto se agrupa en gris como "otro".
CATEGORICAL = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300"]
NEUTRAL = "#a3a29e"
SEQUENTIAL = "Blues"
DIVERGING = "RdBu_r"

# Las figuras se publican como PNG en los .ipynb y GitHub las muestra sobre fondo claro;
# se parte del estilo por defecto para que no hereden el tema oscuro del editor.
plt.style.use("default")
plt.rcParams.update(
    {
        "figure.facecolor": "white",
        "axes.facecolor": "white",
        "savefig.facecolor": "white",
        "text.color": "#0b0b0b",
        "axes.labelcolor": "#0b0b0b",
        "axes.edgecolor": "#52514e",
        "xtick.color": "#52514e",
        "ytick.color": "#52514e",
        "legend.labelcolor": "#0b0b0b",
    }
)

YDATA_SCRIPT = PROJECT_ROOT / "scripts" / "ydata_profile.py"
YDATA_HTML_DIR = PROJECT_ROOT / "docs" / "eda"
YDATA_JSON_DIR = PROJECT_ROOT / "data" / "interim" / "eda"

# Traducción de las alertas de ydata-profiling a una etiqueta corta en español.
ALERT_KINDS = {
    "highly overall correlated": "alta correlación",
    "highly imbalanced": "desbalanceada",
    "missing values": "faltantes",
    "highly skewed": "muy sesgada",
    "has unique values": "valores únicos",
    "zeros": "ceros",
    "constant": "constante",
    "duplicate": "duplicados",
}


def processed_path(dataset: str) -> Path:
    config = load_dataset_config(load_params(), source="agua_hermosillo", dataset=dataset)
    return PROJECT_ROOT / config["processed"]["directory"] / config["processed"]["filename"]


def run_ydata_profile(dataset: str) -> Path:
    """Genera el reporte de ydata-profiling si falta o si el CSV es más nuevo."""
    html = YDATA_HTML_DIR / f"{dataset}.html"
    report_json = YDATA_JSON_DIR / f"{dataset}.json"
    source = processed_path(dataset)
    is_stale = not report_json.exists() or report_json.stat().st_mtime < source.stat().st_mtime
    if is_stale:
        # Corre en su propio entorno: ydata-profiling no es compatible con pandas 3.
        subprocess.run(
            ["uv", "run", "--script", str(YDATA_SCRIPT), dataset], check=True, cwd=PROJECT_ROOT
        )
    return html


def ydata_summary(dataset: str) -> tuple[pd.Series, pd.DataFrame]:
    """Resumen de la tabla y alertas del reporte de ydata-profiling."""
    report = json.loads((YDATA_JSON_DIR / f"{dataset}.json").read_text())
    table = report["table"]
    overview = pd.Series(
        {
            "filas": table["n"],
            "columnas": table["n_var"],
            "celdas faltantes": table["n_cells_missing"],
            "% celdas faltantes": round(100 * table["p_cells_missing"], 2),
            "columnas con faltantes": table["n_vars_with_missing"],
            "filas duplicadas": table["n_duplicates"],
            "memoria (MB)": round(table["memory_size"] / 1e6, 2),
            **{f"tipo {kind}": count for kind, count in table["types"].items()},
        },
        name=dataset,
        dtype=object,
    )

    rows = []
    for alert in report["alerts"]:
        match = re.match(r"\[(?P<column>[^\]]+)\]\s*(?P<message>.*)", alert)
        column, message = match["column"], match["message"]
        kind = next((label for key, label in ALERT_KINDS.items() if key in message), "otra")
        rows.append({"columna": column, "alerta": kind, "detalle": message})
    alerts = pd.DataFrame(rows).sort_values(["alerta", "columna"], ignore_index=True)
    return overview, alerts


def missing_table(frame: pd.DataFrame) -> pd.DataFrame:
    """Nulos y cadenas vacías por columna; solo las columnas que tienen alguno."""
    empty = {
        column: int((frame[column] == "").sum())
        for column in frame.columns
        if pd.api.types.is_string_dtype(frame[column])
    }
    table = pd.DataFrame(
        {
            "nulos": frame.isna().sum(),
            "vacios": pd.Series(empty).reindex(frame.columns).fillna(0).astype(int),
        }
    )
    table["% nulos"] = (100 * table["nulos"] / len(frame)).round(2)
    table["% vacios"] = (100 * table["vacios"] / len(frame)).round(2)
    return table[(table["nulos"] > 0) | (table["vacios"] > 0)].sort_values(
        "% nulos", ascending=False
    )


def cramers_v(x: pd.Series, y: pd.Series) -> float:
    """V de Cramér con corrección de sesgo (Bergsma, 2013)."""
    table = pd.crosstab(x, y)
    if min(table.shape) < 2:
        return np.nan
    chi2 = chi2_contingency(table, correction=False)[0]
    n = table.to_numpy().sum()
    phi2 = chi2 / n
    rows, cols = table.shape
    phi2_corrected = max(0.0, phi2 - (cols - 1) * (rows - 1) / (n - 1))
    rows_corrected = rows - (rows - 1) ** 2 / (n - 1)
    cols_corrected = cols - (cols - 1) ** 2 / (n - 1)
    return float(np.sqrt(phi2_corrected / min(cols_corrected - 1, rows_corrected - 1)))


def cramers_v_matrix(frame: pd.DataFrame, columns: list[str]) -> pd.DataFrame:
    matrix = pd.DataFrame(1.0, index=columns, columns=columns)
    for i, first in enumerate(columns):
        for second in columns[i + 1 :]:
            value = cramers_v(frame[first], frame[second])
            matrix.loc[first, second] = matrix.loc[second, first] = value
    return matrix


def correlation_ratio(categories: pd.Series, values: pd.Series) -> float:
    """Razón de correlación eta: cuánto de la varianza numérica explica la categoría."""
    data = pd.DataFrame({"category": categories, "value": values}).dropna()
    grand_mean = data["value"].mean()
    groups = data.groupby("category", observed=True)["value"]
    between = (groups.count() * (groups.mean() - grand_mean) ** 2).sum()
    total = ((data["value"] - grand_mean) ** 2).sum()
    return float(np.sqrt(between / total)) if total > 0 else np.nan


def iqr_outliers(values: pd.Series, k: float = 1.5) -> pd.Series:
    """Regla de Tukey: fuera de [Q1 - k IQR, Q3 + k IQR]."""
    q1, q3 = values.quantile([0.25, 0.75])
    spread = q3 - q1
    return (values < q1 - k * spread) | (values > q3 + k * spread)


def pyod_outliers(features: pd.DataFrame, contamination: float = 0.02) -> pd.DataFrame:
    """Marca anomalías con tres detectores de PyOD sobre las mismas variables.

    - IForest: aísla puntos con cortes aleatorios; los raros se aíslan en pocos cortes.
    - ECOD: usa las colas de las distribuciones empíricas de cada variable; sin parámetros.
    - LOF: compara la densidad local de cada punto con la de sus vecinos.
    """
    values = features.to_numpy(dtype=float)
    detectors = {
        "iforest": IForest(contamination=contamination, random_state=RANDOM_STATE),
        "ecod": ECOD(contamination=contamination),
        "lof": LOF(contamination=contamination, n_neighbors=20),
    }
    result = pd.DataFrame(index=features.index)
    for name, detector in detectors.items():
        detector.fit(values)
        result[f"{name}_score"] = detector.decision_scores_
        result[f"{name}_outlier"] = detector.labels_.astype(bool)
    flags = result.filter(like="_outlier")
    result["votes"] = flags.sum(axis=1)
    return result


def agreement_table(flags: pd.DataFrame) -> pd.DataFrame:
    """Índice de Jaccard entre los conjuntos de anomalías de cada técnica."""
    names = list(flags.columns)
    table = pd.DataFrame(index=names, columns=names, dtype=float)
    for first in names:
        for second in names:
            union = (flags[first] | flags[second]).sum()
            table.loc[first, second] = (flags[first] & flags[second]).sum() / union if union else 0
    return table.round(2)


def embed_2d(features: np.ndarray, perplexity: float = 30.0) -> dict[str, np.ndarray]:
    """Proyecta a 2D con PCA, t-SNE y UMAP (las tres con la misma semilla)."""
    # UMAP avisa que la semilla lo obliga a usar un solo hilo; es lo que queremos.
    warnings.filterwarnings("ignore", message="n_jobs value", category=UserWarning)
    return {
        "PCA": PCA(n_components=2, random_state=RANDOM_STATE).fit_transform(features),
        "t-SNE": TSNE(
            n_components=2, perplexity=perplexity, init="pca", random_state=RANDOM_STATE
        ).fit_transform(features),
        "UMAP": umap.UMAP(
            n_components=2, n_neighbors=15, min_dist=0.1, random_state=RANDOM_STATE
        ).fit_transform(features),
    }


def embedding_quality(
    features: np.ndarray, embeddings: dict[str, np.ndarray], n_neighbors: int = 10
) -> pd.Series:
    """Confiabilidad (trustworthiness): qué tanto se respetan los vecinos originales en 2D."""
    return pd.Series(
        {
            name: trustworthiness(features, coords, n_neighbors=n_neighbors)
            for name, coords in embeddings.items()
        },
        name="trustworthiness",
    ).round(3)


def category_colors(
    labels: pd.Series, top: int = 3, other: str = "otro"
) -> tuple[pd.Series, dict[str, str]]:
    """Los `top` valores más frecuentes con color propio; el resto queda en gris."""
    keep = [value for value in labels.value_counts().index if value != other][:top]
    palette = dict(zip(keep, CATEGORICAL))
    legend = dict(palette)
    if not labels.isin(keep).all():
        legend[f"{other} y resto"] = NEUTRAL
    return labels.map(palette).fillna(NEUTRAL), legend


def plot_embeddings(
    embeddings: dict[str, np.ndarray],
    labels: pd.Series,
    title: str,
    top: int = 3,
    other: str = "otro",
) -> plt.Figure:
    colors, legend = category_colors(labels.reset_index(drop=True), top=top, other=other)
    fig, axes = plt.subplots(1, len(embeddings), figsize=(5 * len(embeddings), 4.6))
    # El gris va primero para que las categorías con color queden encima.
    order = np.argsort((colors != NEUTRAL).to_numpy(), kind="stable")
    for ax, (name, coords) in zip(axes, embeddings.items()):
        ax.scatter(
            coords[order, 0],
            coords[order, 1],
            c=colors.to_numpy()[order],
            s=8,
            alpha=0.7,
            linewidths=0,
        )
        ax.set_title(name)
        ax.set_xticks([])
        ax.set_yticks([])
        for spine in ax.spines.values():
            spine.set_visible(False)
    handles = [
        plt.Line2D([], [], marker="o", linestyle="", color=color, label=label, markersize=8)
        for label, color in legend.items()
    ]
    fig.legend(handles=handles, loc="lower center", ncol=len(handles), frameon=False)
    fig.suptitle(title)
    fig.tight_layout(rect=(0, 0.07, 1, 1))
    return fig


def plot_heatmap(matrix: pd.DataFrame, title: str, diverging: bool = True) -> plt.Figure:
    size = max(4.5, 0.55 * len(matrix))
    fig, ax = plt.subplots(figsize=(size + 1, size))
    cmap, vmin = (DIVERGING, -1) if diverging else (SEQUENTIAL, 0)
    image = ax.imshow(matrix.to_numpy(dtype=float), cmap=cmap, vmin=vmin, vmax=1)
    ax.set_xticks(range(len(matrix.columns)), matrix.columns, rotation=60, ha="right")
    ax.set_yticks(range(len(matrix.index)), matrix.index)
    for (i, j), value in np.ndenumerate(matrix.to_numpy(dtype=float)):
        if not np.isnan(value):
            color = "white" if abs(value) > 0.6 else "#0b0b0b"
            ax.text(j, i, f"{value:.2f}", ha="center", va="center", fontsize=7, color=color)
    fig.colorbar(image, ax=ax, shrink=0.8)
    ax.set_title(title)
    fig.tight_layout()
    return fig
