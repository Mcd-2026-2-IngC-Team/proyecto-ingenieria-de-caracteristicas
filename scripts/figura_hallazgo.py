"""Dibuja la figura del hallazgo principal: docs/img/hallazgo_principal.svg.

Uso: uv run python scripts/figura_hallazgo.py

Izquierda: lluvia mensual y llamadas al 911 por inundación y por terreno, 2018 a 2025, en
paneles separados con el mismo eje de tiempo (no se comparte eje vertical). Derecha: cuántas
veces sube el conteo diario de cada serie tras una lluvia de 10 mm o más, contra días secos
de la misma temporada. Los números salen de project_name.water_events, igual que en el
notebook 08.
"""

import matplotlib.pyplot as plt
import pandas as pd

from project_name import water_events as we
from project_name.config import PROJECT_ROOT
from project_name.eda import CATEGORICAL, NEUTRAL

OUTPUT = PROJECT_ROOT / "docs" / "img" / "hallazgo_principal.svg"
INK, MUTED = "#0b0b0b", "#52514e"


def main() -> None:
    rain = we.load_rain()
    calls = we.load_calls()
    baches = we.load_baches()
    posts = we.load_posts()

    window = slice("2018-01-01", "2025-09-30")
    monthly_rain = rain[window].resample("MS").sum()
    monthly_calls = {
        label: calls[calls["grupo_incidente"] == group]
        .set_index("date")
        .resample("MS")
        .size()
        .reindex(monthly_rain.index, fill_value=0)
        for label, group in [("inundación", "inundacion_directa"), ("terreno", "terreno")]
    }

    series = {
        "911 inundación": we.daily_counts(
            calls[calls["grupo_incidente"] == "inundacion_directa"], "911"
        ),
        "911 terreno": we.daily_counts(calls[calls["grupo_incidente"] == "terreno"], "911"),
        "911 drenaje": we.daily_counts(
            calls[calls["grupo_incidente"] == "drenaje_y_red_de_agua"], "911"
        ),
        "Baches": we.daily_counts(baches, "baches"),
        "Emergencias AguaH": we.daily_counts(posts[posts["event_type"] == "emergencia"], "aguah"),
    }
    daily = we.daily_table(rain, series)
    ratios = pd.DataFrame([we.event_study(daily, name) for name in series]).sort_values("razón")

    fig = plt.figure(figsize=(12, 5.6))
    grid = fig.add_gridspec(3, 2, width_ratios=[2.1, 1], hspace=0.35, wspace=0.28)
    ax_rain = fig.add_subplot(grid[0, 0])
    ax_flood = fig.add_subplot(grid[1, 0], sharex=ax_rain)
    ax_ground = fig.add_subplot(grid[2, 0], sharex=ax_rain)
    ax_ratio = fig.add_subplot(grid[:, 1])

    width = pd.Timedelta(days=24)
    ax_rain.bar(monthly_rain.index, monthly_rain.values, width=width, color=NEUTRAL)
    ax_flood.bar(
        monthly_calls["inundación"].index,
        monthly_calls["inundación"],
        width=width,
        color=CATEGORICAL[0],
    )
    ax_ground.bar(
        monthly_calls["terreno"].index, monthly_calls["terreno"], width=width, color=CATEGORICAL[1]
    )
    for ax, title in [
        (ax_rain, "Lluvia mensual (mm)"),
        (ax_flood, "Llamadas al 911 por inundación, por mes"),
        (ax_ground, "Llamadas al 911 por terreno (árbol caído, hundimiento, socavón), por mes"),
    ]:
        ax.set_title(title, loc="left", fontsize=9.5, color=INK)
        ax.spines[["top", "right"]].set_visible(False)
        ax.tick_params(labelsize=8, colors=MUTED)
        ax.grid(axis="y", color="#e6e5e1", lw=0.6)
        ax.set_axisbelow(True)
    plt.setp(ax_rain.get_xticklabels(), visible=False)
    plt.setp(ax_flood.get_xticklabels(), visible=False)

    colors = [
        CATEGORICAL[0]
        if name == "911 inundación"
        else CATEGORICAL[1]
        if name == "911 terreno"
        else "#7f9fc4"
        if name == "911 drenaje"
        else NEUTRAL
        for name in ratios["serie"]
    ]
    ax_ratio.barh(ratios["serie"], ratios["razón"], color=colors, height=0.55)
    ax_ratio.axvline(1, color=MUTED, lw=0.8)
    ax_ratio.set_xscale("log")
    ax_ratio.set_xlim(0.5, 60)
    # Los baches suben en la comparación global solo por la tendencia de largo plazo;
    # dentro del mismo mes de cada año la razón queda en 1 (ver notebook 08, E2).
    baches_within = we.within_month_ratio(daily, "Baches")
    baches_within = baches_within["húmedo"].mean() / baches_within["seco"].mean()
    for y, (name, value) in enumerate(zip(ratios["serie"], ratios["razón"])):
        label = f"{value:.1f}×"
        if name == "Baches":
            label += f"\n({baches_within:.2f}× dentro\ndel mismo mes)"
        ax_ratio.text(value * 1.12, y, label, va="center", fontsize=9, color=INK)
    ax_ratio.set_title(
        "Conteo diario tras lluvia de 10 mm o más\nentre conteo en días secos (jun a oct)",
        loc="left",
        fontsize=9.5,
        color=INK,
    )
    ax_ratio.set_xticks([0.5, 1, 2, 5, 10, 20, 50], ["0.5", "1", "2", "5", "10", "20", "50"])
    ax_ratio.tick_params(labelsize=8.5, colors=MUTED)
    ax_ratio.spines[["top", "right"]].set_visible(False)

    fig.suptitle(
        "En Hermosillo la lluvia dispara las emergencias urbanas del 911, no los baches ni las "
        "emergencias de agua potable",
        x=0.01,
        y=1.03,
        ha="left",
        fontsize=11.5,
        color=INK,
    )
    fig.text(
        0.01,
        0.005,
        "Fuentes: llamadas al 911 2018 a 2025 (Marcelinux, Hugging Face); Open-Meteo; "
        "Bachómetro de Hermosillo; publicaciones de Agua de Hermosillo.",
        fontsize=7.5,
        color=MUTED,
    )
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(OUTPUT, bbox_inches="tight")
    fig.savefig(OUTPUT.with_suffix(".png"), dpi=150, bbox_inches="tight")
    # Vectorial para el reporte en LaTeX (docs/reporte/).
    fig.savefig(OUTPUT.with_suffix(".pdf"), bbox_inches="tight")
    print(f"Figura guardada en {OUTPUT}")


if __name__ == "__main__":
    main()
