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
    # Análisis exploratorio: colonias de Hermosillo

    `colonias_hermosillo.csv` es el catálogo de asentamientos del municipio según el DCAH 2025
    del INEGI: una fila por colonia, fraccionamiento o residencial, con su clave, nombre,
    tipo, código postal, área y centroide. Es el catálogo contra el que se resuelven las
    colonias que nombran los avisos, así que su calidad decide la del desglose territorial.

    El catálogo por sí solo tiene pocas variables numéricas (área y centroide). Para que las
    relaciones, la correlación y la reducción de dimensión digan algo sobre el problema, a
    cada colonia se le agregan variables que salen de los otros dos datasets tidy del
    proyecto: cuántas publicaciones la mencionan, cómo se resolvieron esas menciones y cuánto
    enojo generaron esas publicaciones.

    ## Objetivos

    1. Auto EDA con ydata-profiling, publicado en `docs/eda/`.
    2. Datos faltantes, incluidos los que el catálogo codifica como valores válidos.
    3. Anomalías con regla de Tukey y PyOD (IForest, ECOD y LOF).
    4. Relaciones entre variables por visualización.
    5. Correlación entre variables numéricas y categóricas.
    6. Reducción a 2D con PCA, t-SNE y UMAP.
    7. Preguntas para los usuarios.
    """)
    return


@app.cell
def _():
    import matplotlib.pyplot as plt
    import numpy as np
    import pandas as pd
    from sklearn.decomposition import PCA
    from sklearn.preprocessing import StandardScaler

    from project_name.eda import (
        CATEGORICAL,
        NEUTRAL,
        agreement_table,
        category_colors,
        correlation_ratio,
        cramers_v_matrix,
        embed_2d,
        embedding_quality,
        iqr_outliers,
        missing_table,
        plot_embeddings,
        plot_heatmap,
        processed_path,
        pyod_outliers,
        run_ydata_profile,
        ydata_summary,
    )

    DATASET = "colonias_hermosillo"
    pd.set_option("display.max_rows", 60)
    return (
        CATEGORICAL,
        DATASET,
        NEUTRAL,
        PCA,
        StandardScaler,
        agreement_table,
        category_colors,
        correlation_ratio,
        cramers_v_matrix,
        embed_2d,
        embedding_quality,
        iqr_outliers,
        missing_table,
        np,
        pd,
        plot_embeddings,
        plot_heatmap,
        plt,
        processed_path,
        pyod_outliers,
        run_ydata_profile,
        ydata_summary,
    )


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## 1. Auto EDA con ydata-profiling

    Reporte completo:
    [`docs/eda/colonias_hermosillo.html`](../../docs/eda/colonias_hermosillo.html), generado
    por `scripts/ydata_profile.py` en su propio entorno (ydata-profiling 4.18 exige
    pandas<3). Las claves (`colonia_id`, `locality_code`, `postal_code`) se leen como texto
    para que el reporte no las trate como cantidades.
    """)
    return


@app.cell
def _(DATASET, run_ydata_profile, ydata_summary):
    report_html = run_ydata_profile(DATASET)
    ydata_overview, ydata_alerts = ydata_summary(DATASET)
    ydata_overview.to_frame("valor")
    return (ydata_alerts,)


@app.cell
def _(ydata_alerts):
    ydata_alerts
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    El reporte no encuentra nulos ni duplicados. Sus alertas apuntan a otra cosa: la
    localidad, la fecha de actualización, el código postal y el centroide se mueven juntos, y
    `postal_code` tiene 20 "ceros". Las dos cosas tienen la misma causa, que se revisa en la
    sección 2: el catálogo mezcla la ciudad con dos localidades rurales.
    """)
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## 2. Datos faltantes
    """)
    return


@app.cell
def _(DATASET, pd, processed_path):
    colonias = pd.read_csv(
        processed_path(DATASET),
        dtype={"colonia_id": str, "locality_code": str, "postal_code": str},
    )
    colonias.shape
    return (colonias,)


@app.cell
def _(colonias, missing_table):
    missing_table(colonias)
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    No hay nulos ni cadenas vacías. Pero un catálogo puede codificar el faltante como un valor
    válido. Se buscan tres casos: el código postal `00000` (el diccionario dice "00000 si no
    lo reportó"), el tipo de asentamiento `NINGUNO` y la fecha de actualización distinta a la
    del resto.
    """)
    return


@app.cell
def _(colonias, pd):
    LOCALITIES = {"0001": "Hermosillo (ciudad)", "0137": "Bahía de Kino", "0343": "Miguel Alemán"}
    hidden_missing = {
        "postal_code = 00000": colonias["postal_code"] == "00000",
        "settlement_type = NINGUNO": colonias["settlement_type"] == "NINGUNO",
        "updated_at = 11/2022": colonias["updated_at"] == "11/2022",
    }
    pd.DataFrame(
        {
            rule: colonias.loc[mask, "locality_code"].map(LOCALITIES).value_counts()
            for rule, mask in hidden_missing.items()
        }
    ).fillna(0).astype(int).T.assign(total=lambda frame: frame.sum(axis=1))
    return (LOCALITIES,)


@app.cell
def _(colonias):
    colonias.loc[
        colonias["settlement_type"] == "NINGUNO",
        ["colonia_id", "settlement_name", "postal_code", "area_km2"],
    ]
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    - Los 20 códigos postales `00000` son todos de Bahía de Kino (12) y Miguel Alemán (8):
      el municipio no reportó código postal para esas localidades. Faltante MNAR
      (depende de la localidad, que sí está en la tabla). Se deja como nulo al analizar; no
      se imputa porque el código postal no se usa para emparejar avisos.
    - Los 4 `NINGUNO` son lugares comerciales (Plaza de las Franquicias, Central de Abastos,
      Comercial Cedros) y Altares; es una categoría real del INEGI, no un faltante.
    - Los 21 asentamientos con `updated_at = 11/2022` son exactamente los de Bahía de Kino y
      Miguel Alemán: el municipio no los actualizó en 2025.

    Hay otra forma de faltante que importa para el proyecto: colonias del catálogo que ningún
    aviso menciona. Para medirla se cruzan las colonias con `ubicaciones_aviso`.
    """)
    return


@app.cell
def _(colonias, pd, processed_path):
    locations = pd.read_csv(
        processed_path("ubicaciones_aviso"), dtype={"post_id": str, "colonia_id": str}
    )
    posts = pd.read_csv(
        processed_path("publicaciones_aguah"),
        dtype={"post_id": str},
        usecols=["post_id", "event_type", "angry_share", "reactions_total"],
    )
    # Una colonia puede salir dos veces en el mismo aviso (por nombre y por un cruce); para
    # contar publicaciones por colonia basta una vez.
    mentions = (
        locations.dropna(subset=["colonia_id"])
        .merge(posts, on="post_id", how="left")
        .assign(
            is_cross=lambda frame: frame["location_type"] == "cruce",
            from_ocr=lambda frame: frame["source_field"] != "texto",
            explicit=lambda frame: frame["match_method"] != "colonia_en_catalogo",
        )
    )
    mention_features = mentions.groupby("colonia_id").agg(
        n_mentions=("post_id", "size"),
        n_posts=("post_id", "nunique"),
        share_cross=("is_cross", "mean"),
        share_ocr=("from_ocr", "mean"),
        share_explicit=("explicit", "mean"),
        angry_share_mean=("angry_share", "mean"),
        share_emergency=("event_type", lambda s: (s == "emergencia").mean()),
    )
    colonia_profile = colonias.merge(mention_features, on="colonia_id", how="left").assign(
        mentioned=lambda frame: frame["n_posts"].notna(),
        n_posts=lambda frame: frame["n_posts"].fillna(0),
        n_mentions=lambda frame: frame["n_mentions"].fillna(0),
        log_area=lambda frame: frame["area_km2"].apply("log"),
    )
    colonia_profile.shape
    return colonia_profile, locations


@app.cell
def _(LOCALITIES, colonia_profile, pd):
    pd.crosstab(
        colonia_profile["locality_code"].map(LOCALITIES),
        colonia_profile["mentioned"].map({True: "mencionada", False: "nunca mencionada"}),
        margins=True,
    )
    return


@app.cell
def _(colonia_profile, pd):
    pd.crosstab(
        colonia_profile["settlement_type"],
        colonia_profile["mentioned"],
        normalize="index",
    ).mul(100).round(1).rename(columns={True: "% mencionada", False: "% nunca"}).join(
        colonia_profile["settlement_type"].value_counts().rename("colonias")
    ).sort_values("colonias", ascending=False)
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    562 de las 783 colonias (72%) aparecen en al menos un aviso; 221 nunca. De estas, 206 son
    de la ciudad. Las colonias tradicionales casi siempre aparecen y los fraccionamientos,
    residenciales y privadas mucho menos. En el tablero, "sin avisos" no debe pintarse igual
    que "cero problemas": puede ser una colonia que el organismo nombra de otra forma o que se
    abastece de otra red.

    Las variables de menciones (`share_cross`, `share_ocr`, `share_explicit`,
    `angry_share_mean`, `share_emergency`) no están definidas para las colonias nunca
    mencionadas. Se dejan nulas para describir y se llenan con 0, junto con la bandera
    `mentioned`, solo en las técnicas que no aceptan nulos (PyOD, PCA, t-SNE y UMAP).
    """)
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ### Nombres repetidos

    Los avisos nombran colonias, no claves. Si dos asentamientos se llaman igual, el aviso es
    ambiguo.
    """)
    return


@app.cell
def _(colonias):
    duplicated_names = colonias[
        colonias["settlement_name_normalized"].duplicated(keep=False)
    ].sort_values(["settlement_name_normalized", "settlement_type"])
    print(
        f"{duplicated_names['settlement_name_normalized'].nunique()} nombres repetidos en "
        f"{len(duplicated_names)} asentamientos"
    )
    duplicated_names[
        ["settlement_name", "settlement_type", "locality_code", "postal_code", "area_km2"]
    ]
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    18 nombres corresponden a 38 asentamientos. Casi siempre es una colonia y su ampliación,
    privada o etapa con el mismo nombre (4 de Marzo, El Mirador, Ladrilleras), con el mismo
    código postal. Un aviso que dice "4 de Marzo" no permite saber cuál de las dos es.
    """)
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## 3. Anomalías

    1. Univariada: regla de Tukey sobre el área, en escala original y en logaritmo (el área va
       de 0.0009 a 4.49 km², con sesgo fuerte a la derecha).
    2. Multivariada con PyOD sobre logaritmo del área, latitud, longitud y `log1p(n_posts)`,
       estandarizadas, con `contamination=0.03` (24 colonias por detector).
    """)
    return


@app.cell
def _(colonia_profile, iqr_outliers, pd):
    tukey_area = pd.DataFrame(
        {
            "area_km2": iqr_outliers(colonia_profile["area_km2"]),
            "log_area": iqr_outliers(colonia_profile["log_area"]),
        }
    )
    tukey_area.sum().rename("anómalas (Tukey)").to_frame()
    return (tukey_area,)


@app.cell
def _(colonia_profile, tukey_area):
    colonia_profile.loc[
        tukey_area["log_area"], ["settlement_name", "settlement_type", "area_km2", "n_posts"]
    ].sort_values("area_km2")
    return


@app.cell
def _(StandardScaler, agreement_table, colonia_profile, np, pd, pyod_outliers, tukey_area):
    _features = colonia_profile[["log_area", "centroid_lat", "centroid_lon"]].assign(
        log_posts=np.log1p(colonia_profile["n_posts"])
    )
    _scaled = pd.DataFrame(StandardScaler().fit_transform(_features), columns=_features.columns)
    colonia_outliers = pyod_outliers(_scaled, contamination=0.03)
    agreement_table(
        colonia_outliers.filter(like="_outlier").assign(tukey_log_area=tukey_area["log_area"])
    )
    return (colonia_outliers,)


@app.cell
def _(LOCALITIES, colonia_outliers, colonia_profile):
    colonia_profile.loc[
        colonia_outliers["votes"] >= 2,
        ["settlement_name", "settlement_type", "locality_code", "area_km2", "n_posts"],
    ].assign(
        localidad=lambda frame: frame["locality_code"].map(LOCALITIES),
        votos=colonia_outliers["votes"],
    ).sort_values(["localidad", "n_posts"], ascending=[True, False])
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    IForest y ECOD coinciden en 55% de sus marcas; LOF casi no coincide con ellos (7% a 17%)
    y se parece más a Tukey sobre el área (31%), porque marca puntos aislados en su vecindad.
    Las 21 colonias marcadas por al menos dos detectores forman dos grupos:

    - Geográficas: 11 asentamientos de Bahía de Kino y 3 de Miguel Alemán, a 50 y 100 km de
      la ciudad. No son errores, pero sí otra población: el tablero de la ciudad debería
      filtrarlos o mostrarlos aparte.
    - De tamaño y menciones: Centro, Altares, Palo Verde, Nuevo Hermosillo y tres parques
      industriales, las colonias más grandes o más mencionadas de la ciudad.

    Tukey sobre el logaritmo del área encuentra además los asentamientos diminutos (un
    condominio de 900 m², privadas y etapas de 2,000 a 4,000 m²), que son reales. Sobre el
    área sin logaritmo marca 74, casi todo colonias grandes normales: con sesgo tan fuerte la
    regla necesita la transformación.

    Lo que sí parece un error es que haya colonias rurales mencionadas en avisos del organismo
    de agua de la ciudad. La tabla siguiente muestra qué texto produjo esas menciones:
    """)
    return


@app.cell
def _(LOCALITIES, colonias, locations):
    _rural = colonias.loc[
        colonias["locality_code"] != "0001", ["colonia_id", "settlement_name", "locality_code"]
    ]
    locations.merge(_rural, on="colonia_id").assign(
        localidad=lambda frame: frame["locality_code"].map(LOCALITIES)
    ).groupby(["localidad", "settlement_name", "raw_text", "match_method"]).size().rename(
        "menciones"
    ).sort_values(ascending=False).to_frame()
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    Hay 58 menciones resueltas a colonias rurales; 51 por `colonia_en_catalogo` (el nombre
    suelto) y 7 con marcador ("colonia Los Viñedos", "colonia Las Fuentes"). Son nombres que
    en la ciudad corresponden a otra cosa (un fraccionamiento que el DCAH registra con otro
    nombre, una calle o bulevar como Salvador Alvarado, o una etiqueta genérica como "Sector
    A") y que el emparejamiento resolvió a la única coincidencia del catálogo, en Kino o
    Miguel Alemán. Son falsos positivos probables del proceso de `ubicaciones_aviso`: conviene
    restringir el catálogo de emparejamiento a la localidad 0001 o confirmarlo con los
    usuarios (pregunta 3).
    """)
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## 4. Relaciones entre variables por visualización
    """)
    return


@app.cell
def _(NEUTRAL, category_colors, colonia_profile, plt):
    _city = colonia_profile[colonia_profile["locality_code"] == "0001"]
    _colors, _legend = category_colors(_city["settlement_type"], top=3, other="otro")
    _fig, _axes = plt.subplots(1, 2, figsize=(13, 6))
    _axes[0].scatter(
        _city["centroid_lon"],
        _city["centroid_lat"],
        s=8 + 60 * _city["area_km2"],
        c=_colors,
        alpha=0.75,
        edgecolors="white",
        linewidths=0.4,
    )
    _axes[0].set_title("Tipo de asentamiento (tamaño: área)")
    for _label, _color in _legend.items():
        _axes[0].scatter([], [], color=_color, label=_label, s=30)
    _axes[0].legend(frameon=False, loc="lower left", fontsize=8)
    _never = _city["n_posts"] == 0
    _scatter = _axes[1].scatter(
        _city.loc[~_never, "centroid_lon"],
        _city.loc[~_never, "centroid_lat"],
        s=14,
        c=_city.loc[~_never, "n_posts"].pipe(lambda s: s.clip(upper=s.quantile(0.95))),
        cmap="Blues",
        edgecolors="#52514e",
        linewidths=0.2,
    )
    _axes[1].scatter(
        _city.loc[_never, "centroid_lon"],
        _city.loc[_never, "centroid_lat"],
        s=14,
        marker="x",
        color=NEUTRAL,
        linewidths=0.8,
        label="nunca mencionada",
    )
    _axes[1].legend(frameon=False, loc="lower left", fontsize=8)
    _axes[1].set_title("Publicaciones que mencionan la colonia")
    _fig.colorbar(_scatter, ax=_axes[1], shrink=0.7, label="n_posts (recortado al p95)")
    for _ax in _axes:
        _ax.set_aspect("equal")
        _ax.set_xticks([])
        _ax.set_yticks([])
        _ax.spines[:].set_visible(False)
    _fig.suptitle("Centroides de las colonias de la ciudad (localidad 0001)")
    _fig.tight_layout()
    _fig
    return


@app.cell
def _(CATEGORICAL, NEUTRAL, colonia_profile, plt):
    _city = colonia_profile[
        (colonia_profile["locality_code"] == "0001") & colonia_profile["mentioned"]
    ]
    _palette = {"COLONIA": CATEGORICAL[0], "FRACCIONAMIENTO": CATEGORICAL[1]}
    _fig, _axes = plt.subplots(1, 2, figsize=(13, 4.5))
    for _type in ["otro", "FRACCIONAMIENTO", "COLONIA"]:
        _subset = (
            _city[~_city["settlement_type"].isin(_palette)]
            if _type == "otro"
            else _city[_city["settlement_type"] == _type]
        )
        _color = _palette.get(_type, NEUTRAL)
        _axes[0].scatter(
            _subset["area_km2"],
            _subset["n_posts"],
            s=12,
            color=_color,
            alpha=0.7,
            edgecolors="white",
            linewidths=0.3,
            label=_type.lower(),
        )
        _axes[1].scatter(
            _subset["share_explicit"],
            _subset["angry_share_mean"],
            s=12,
            color=_color,
            alpha=0.7,
            edgecolors="white",
            linewidths=0.3,
            label=_type.lower(),
        )
    _axes[0].set_xscale("log")
    _axes[0].set_yscale("log")
    _axes[0].set_xlabel("área (km², escala log)")
    _axes[0].set_ylabel("publicaciones que la mencionan (log)")
    _axes[0].set_title(
        f"Área y menciones (Spearman {_city['area_km2'].corr(_city['n_posts'], method='spearman'):.2f})"
    )
    _axes[1].set_xlabel("proporción de menciones explícitas o por cruce")
    _axes[1].set_ylabel("angry_share medio de sus publicaciones")
    _axes[1].set_title("Cómo se resolvió la mención y enojo")
    for _ax in _axes:
        _ax.legend(frameon=False, fontsize=8)
        _ax.spines[["top", "right"]].set_visible(False)
    _fig.tight_layout()
    _fig
    return


@app.cell
def _(colonia_profile):
    colonia_profile.groupby("settlement_type").agg(
        colonias=("colonia_id", "size"),
        area_mediana_km2=("area_km2", "median"),
        publicaciones_mediana=("n_posts", "median"),
        publicaciones_max=("n_posts", "max"),
    ).sort_values("colonias", ascending=False).round(3)
    return


@app.cell
def _(colonia_profile):
    colonia_profile.nlargest(12, "n_posts")[
        [
            "settlement_name",
            "settlement_type",
            "area_km2",
            "n_posts",
            "share_explicit",
            "share_cross",
        ]
    ].round(2)
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    - En el mapa, las colonias tradicionales ocupan el centro y los fraccionamientos la
      periferia; las colonias nunca mencionadas se reparten por toda la mancha urbana, sin
      una zona vacía.
    - Las colonias más mencionadas (Centro con 390 publicaciones, Solidaridad 312, Sahuaro
      310, Olivares 214) son colonias antiguas y grandes; las menciones crecen con el área
      (Spearman 0.43 entre las mencionadas).
    - Las colonias tradicionales tienen mediana de 19.5 publicaciones; los fraccionamientos,
      de 2.
    - En "Centro", "Solidaridad" y "Sahuaro" menos de un tercio de las menciones es explícita
      ("colonia X") o por cruce: el resto es el nombre suelto, que también es el de un sector
      ("sector Centro"), un bulevar (Solidaridad) o una zona amplia. Su conteo probablemente
      está inflado.
    - Las colonias con más menciones explícitas tienen menos enojo medio (gráfica derecha).
    """)
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## 5. Correlación
    """)
    return


@app.cell
def _(colonia_profile, plot_heatmap):
    profile_numeric = [
        "area_km2",
        "centroid_lat",
        "centroid_lon",
        "n_posts",
        "n_mentions",
        "share_cross",
        "share_ocr",
        "share_explicit",
        "angry_share_mean",
        "share_emergency",
    ]
    _city = colonia_profile[colonia_profile["locality_code"] == "0001"]
    plot_heatmap(
        _city[profile_numeric].corr("spearman"),
        "Spearman, colonias de la ciudad (variables de menciones solo en las mencionadas)",
    )
    return (profile_numeric,)


@app.cell
def _(colonia_profile, cramers_v_matrix, plot_heatmap):
    _categorical = colonia_profile.assign(
        postal_code_missing=colonia_profile["postal_code"] == "00000",
        mentioned=colonia_profile["mentioned"],
    ).astype({"postal_code_missing": str, "mentioned": str})
    plot_heatmap(
        cramers_v_matrix(
            _categorical,
            ["settlement_type", "locality_code", "updated_at", "postal_code_missing", "mentioned"],
        ),
        "V de Cramér entre categóricas",
        diverging=False,
    )
    return


@app.cell
def _(colonia_profile, correlation_ratio, np, pd):
    pd.Series(
        {
            "log(area_km2)": correlation_ratio(
                colonia_profile["settlement_type"], colonia_profile["log_area"]
            ),
            "log1p(n_posts)": correlation_ratio(
                colonia_profile["settlement_type"], np.log1p(colonia_profile["n_posts"])
            ),
            "angry_share_mean": correlation_ratio(
                colonia_profile["settlement_type"], colonia_profile["angry_share_mean"]
            ),
        },
        name="eta con settlement_type",
    ).round(3).to_frame()
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    - `locality_code`, `updated_at` y el código postal `00000` son prácticamente la misma
      variable (V de Cramér cercana a 1): todo lo rural se actualizó en 2022 y no tiene código
      postal. Basta con `locality_code`.
    - `share_cross` y `share_explicit` están muy correlacionadas (0.79) porque los cruces
      cuentan como menciones explícitas; y ambas van en contra de `share_ocr` (-0.47 y
      -0.45): los volantes casi nunca traen cruces ni la palabra "colonia", traen listas de
      nombres.
    - `angry_share_mean` correlaciona en negativo con `share_explicit` (-0.46) y en positivo
      con la latitud (0.32) y con `n_posts` (0.32): las colonias que aparecen sobre todo en
      listas, las del norte y las más mencionadas acumulan avisos con más enojo.
    - `n_posts` y `n_mentions` son la misma variable (1.00): una colonia rara vez se menciona
      dos veces en un aviso.
    - `settlement_type` explica parte del área (eta 0.34) y del número de publicaciones
      (eta 0.37), sobre todo por la diferencia entre colonias y fraccionamientos.
    """)
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## 6. Reducción de dimensión para visualización

    Variables (estandarizadas): logaritmo del área, latitud, longitud, `log1p(n_posts)`,
    `mentioned` y las cinco proporciones de menciones (0 si la colonia no se menciona). Se
    usan solo las 762 colonias de la ciudad, porque las rurales dominarían la latitud y la
    longitud y la proyección solo separaría ciudad de campo. Con 762 filas, t-SNE usa
    perplejidad 30.
    """)
    return


@app.cell
def _(StandardScaler, colonia_profile, np):
    city_profile = colonia_profile[colonia_profile["locality_code"] == "0001"].reset_index(
        drop=True
    )
    _shares = ["share_cross", "share_ocr", "share_explicit", "angry_share_mean", "share_emergency"]
    city_features = (
        city_profile[["log_area", "centroid_lat", "centroid_lon"]]
        .assign(
            log_posts=np.log1p(city_profile["n_posts"]),
            mentioned=city_profile["mentioned"].astype(int),
        )
        .join(city_profile[_shares].fillna(0))
    )
    city_matrix = StandardScaler().fit_transform(city_features)
    city_matrix.shape
    return city_features, city_matrix, city_profile


@app.cell
def _(PCA, city_features, city_matrix, pd):
    _pca = PCA().fit(city_matrix)
    print(
        "Varianza explicada acumulada:",
        _pca.explained_variance_ratio_.cumsum().round(2)[:5].tolist(),
    )
    pd.DataFrame(
        _pca.components_[:2].T, index=city_features.columns, columns=["PC1", "PC2"]
    ).round(2).sort_values("PC1")
    return


@app.cell
def _(city_matrix, embed_2d):
    city_embeddings = embed_2d(city_matrix)
    return (city_embeddings,)


@app.cell
def _(city_embeddings, city_profile, plot_embeddings):
    plot_embeddings(
        city_embeddings,
        city_profile["settlement_type"],
        "Colonias de la ciudad, color por tipo de asentamiento",
        top=3,
    )
    return


@app.cell
def _(city_embeddings, city_profile, np, pd, plot_embeddings):
    _activity = pd.cut(
        city_profile["n_posts"],
        bins=[-np.inf, 0, 10, np.inf],
        labels=["nunca mencionada", "1 a 10 publicaciones", "más de 10"],
    ).astype(str)
    plot_embeddings(
        city_embeddings,
        _activity,
        "Colonias de la ciudad, color por publicaciones que las mencionan",
    )
    return


@app.cell
def _(city_embeddings, city_matrix, embedding_quality):
    embedding_quality(city_matrix, city_embeddings).to_frame()
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    - PCA: las dos primeras componentes explican 54% de la varianza. PC1 es la actividad en
      avisos (`mentioned`, `log_posts`, `angry_share_mean`); PC2 opone las menciones
      explícitas o por cruce (0.61 y 0.62) a las que salen del OCR (-0.32). El área y la
      ubicación casi no pesan en ninguna.
    - Las tres proyecciones separan un grupo compacto: las 206 colonias nunca mencionadas,
      que tienen todas sus proporciones en 0. t-SNE y UMAP separan además, dentro de las
      mencionadas, las de 1 a 10 publicaciones de las de más de 10.
    - Los tipos de asentamiento se mezclan en las tres: el tipo no define un perfil propio una
      vez que se conoce la actividad.
    - Trustworthiness de 0.90 (PCA) a 0.98 (t-SNE): con 10 variables y 762 filas, PCA ya es
      fiel y más fácil de explicar.
    """)
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## 7. Consulta con los usuarios

    | # | Hallazgo | Pregunta |
    |---|---|---|
    | 1 | 221 colonias (28%) nunca aparecen en un aviso, sobre todo fraccionamientos y privadas | ¿Esas colonias se abastecen de otra red, o el organismo las nombra de otra forma (por sector, por calle)? ¿Cómo quieren verlas en el mapa? |
    | 2 | "Centro", "Solidaridad" y "Sahuaro" se cuentan sobre todo por el nombre suelto, que también es un sector o un bulevar | ¿Cuando un aviso dice "Centro" o "Solidaridad" se refiere a la colonia o a una zona más amplia? |
    | 3 | Hay menciones resueltas a colonias de Bahía de Kino y Miguel Alemán | ¿Agua de Hermosillo da servicio en esas localidades? Si no, se excluyen del emparejamiento. |
    | 4 | 18 nombres se repiten en 38 asentamientos (colonia y su ampliación o privada) | ¿Les basta ver la colonia principal, o necesitan distinguir la ampliación? |
    | 5 | Las colonias del norte y las que aparecen en listas largas acumulan avisos con más enojo | ¿Coincide con su experiencia? ¿Hay zonas que esperarían ver y no aparecen? |
    """)
    return


if __name__ == "__main__":
    app.run()
