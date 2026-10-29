# Análisis exploratorio de los datos tidy

Corte: 26 de octubre de 2026, sobre `data/processed/aguah/` del snapshot del 3 de octubre.

## Artefactos

- `notebooks/05-eda-publicaciones-aguah.ipynb` (fuente: `notebooks/marimo/05-eda-publicaciones-aguah.py`):
  `publicaciones_aguah.csv`, 5,200 × 32.
- `notebooks/06-eda-colonias-hermosillo.ipynb` (fuente: `notebooks/marimo/06-eda-colonias-hermosillo.py`):
  `colonias_hermosillo.csv`, 783 × 10, más variables de menciones agregadas desde
  `ubicaciones_aviso` y `publicaciones_aguah`.
- `notebooks/07-eda-ubicaciones-aviso.ipynb` (fuente: `notebooks/marimo/07-eda-ubicaciones-aviso.py`):
  `ubicaciones_aviso.csv`, 16,261 × 8, más la huella territorial de cada publicación (3,788).
- Auto EDA de ydata-profiling 4.18.4: [`eda/publicaciones_aguah.html`](eda/publicaciones_aguah.html),
  [`eda/colonias_hermosillo.html`](eda/colonias_hermosillo.html),
  [`eda/ubicaciones_aviso.html`](eda/ubicaciones_aviso.html). Los genera `make profile`
  (`scripts/ydata_profile.py`, entorno aislado porque ydata-profiling exige pandas<3).
- Auto EDA del consolidado de subcuencas (una capa por reporte):
  [`eda/subc_hermosillo_hl.html`](eda/subc_hermosillo_hl.html) (red hidrográfica),
  [`eda/subc_hermosillo_dr.html`](eda/subc_hermosillo_dr.html) (puntos de drenaje),
  [`eda/subc_hermosillo_subc.html`](eda/subc_hermosillo_subc.html) (unidades de captación),
  [`eda/subc_hermosillo_ha.html`](eda/subc_hermosillo_ha.html) (cuerpos de agua),
  [`eda/subc_hermosillo_to.html`](eda/subc_hermosillo_to.html) (topónimos).
- Funciones comunes: `project_name/eda.py`.

## Datos faltantes

| Dataset | Columna | Faltantes | Mecanismo | Tratamiento |
|---|---|---:|---|---|
| publicaciones | `announced_duration_hours` | 4,643 (89.3%) | El aviso no declara plazo | Sin imputar |
| publicaciones | `announced_start_at` | 3,640 (70.0%) | MAR: 5% en `corte_programado`, 84% en `emergencia` | Sin imputar; `has_announced_start_at` |
| publicaciones | `angry_share` | 29 (0.6%) | Estructural: `reactions_total = 0` en las 29 | Nulo; 0 en PyOD y proyecciones |
| publicaciones | `ocr_text` vacío | 2,853 (54.9%) | 1,979 sin imagen, 874 con imagen sin texto | No es faltante |
| publicaciones | `top_comment_text` vacío | 1,225 (23.6%) | 657 sin comentarios, 568 sin destacado | No es faltante |
| publicaciones | `text` vacío | 45 (0.9%) | Publicación solo con imagen | No es faltante |
| publicaciones | periodo 5 a 19 de abril de 2024 | 13 días sin publicaciones | Hueco entre exportaciones del scraper | Cobertura incompleta |
| publicaciones | agosto y septiembre de 2026 | 36 y 16 publicaciones (meses previos: 120 a 132) | Probable corte de la última exportación | Cobertura incompleta |
| colonias | `postal_code = 00000` | 20 (2.6%) | MNAR: todas en Bahía de Kino (12) y Miguel Alemán (8) | Nulo al analizar |
| colonias | sin menciones en avisos | 221 (28.2%), 206 en la ciudad | Fraccionamientos, residenciales y privadas sobre todo | Bandera `mentioned` |
| ubicaciones | `lat`, `lon` | 14,794 (91.0%) | Estructural: solo `cruce_geocodificado` tiene punto | Sin imputar; centroide de la colonia |
| ubicaciones | `colonia_id` | 383 (2.4%) | MAR: exactamente `unmatched`; 33% de los cruces del OCR, 20% del texto | Excluir de conteos por colonia |

- `pd.read_csv` convierte la cadena vacía en `NaN`; los notebooks leen `publicaciones_aguah.csv`
  con `keep_default_na=False` para separar vacíos de nulos.
- Sin filas duplicadas en los tres datasets. En `ubicaciones_aviso`, 758 filas repiten un par
  `(post_id, colonia_id)` en 751 publicaciones.

## Anomalías

| Dataset | Variables | Técnica | Marcados | Coincidencia (Jaccard) |
|---|---|---|---:|---|
| publicaciones | `log1p` de reacciones, enojo, comentarios, compartidos, likes del comentario; `angry_share` | Tukey por variable | 701 con alguna variable | 0.15 con IForest y ECOD |
| publicaciones | mismas, estandarizadas | IForest, ECOD, LOF (`contamination=0.02`) | 104, 104, 103; 77 con 2 o más votos | IForest y ECOD 0.58; LOF 0.05 a 0.06 |
| colonias | `log(area_km2)` | Tukey | 14 (74 sin logaritmo) | 0.09 a 0.31 con PyOD |
| colonias | log del área, centroide, `log1p(n_posts)` | IForest, ECOD, LOF (`contamination=0.03`) | 24 cada uno; 21 con 2 o más votos | IForest y ECOD 0.55; LOF 0.07 a 0.17 |
| ubicaciones | menciones por publicación (log) | Tukey | 57 publicaciones (32 a 91 menciones) | |
| ubicaciones | distancia del cruce al centroide / raíz del área | Tukey | 40 cruces | 0.06 con PyOD |
| ubicaciones | lat, lon, distancia al centroide | IForest, ECOD, LOF (`contamination=0.02`) | 30, 30, 29 | IForest y ECOD 0.43; LOF 0.04 a 0.05 |

| Dataset | Anomalía | Filas | Tipo |
|---|---|---:|---|
| publicaciones | `likes_count` idéntica a `reactions_total` | 5,200 | Columna redundante |
| publicaciones | `has_image` verdadero con `ocr_status = skipped_no_image` | 19 | Hueco del OCR |
| publicaciones | Publicadas entre 0:00 y 5:59 | 16 | Avisos reales |
| publicaciones | 77 con interacción extrema: 27% `emergencia` (16% en el total), 9% `corte_programado` (6%) | 77 | Avisos reales |
| colonias | Asentamientos de Bahía de Kino y Miguel Alemán | 21 | Otra población |
| colonias | Menciones en avisos resueltas a colonias rurales (Los Viñedos 20, Las Fuentes 14, Salvador Alvarado 10, Mediterráneo 7, Sector A 6) | 58 menciones | Probables falsos positivos del emparejamiento |
| colonias | Nombres normalizados repetidos | 18 nombres, 38 asentamientos | Ambigüedad para emparejar |
| ubicaciones | Cruce a más de 1.2 radios de su colonia, sobre bulevares | 40 | Asignación ambigua |
| ubicaciones | Cruce más lejano de su centroide | 2.5 km | Sin cruces fuera de la ciudad |

## Correlación

| Dataset | Par | Medida | Valor |
|---|---|---|---:|
| publicaciones | `reactions_total`, `likes_count` | Spearman | 1.00 |
| publicaciones | `reactions_angry`, `angry_share` | Spearman | 0.94 |
| publicaciones | `reactions_total`, `comments_count` | Spearman | 0.75 |
| publicaciones | `reactions_angry`, `comments_count` | Spearman | 0.66 |
| publicaciones | `reactions_angry`, `shares_count` | Spearman | 0.38 |
| publicaciones | `ocr_status`, `has_image` | V de Cramér | 0.99 |
| publicaciones | `event_type`, `has_announced_start_at` | V de Cramér | 0.36 |
| publicaciones | `event_type`, métricas de interacción | eta | 0.06 a 0.12 |
| colonias | `locality_code`, `updated_at` | V de Cramér | 1.00 |
| colonias | `locality_code`, `postal_code = 00000` | V de Cramér | 0.98 |
| colonias | `area_km2`, `n_posts` (ciudad) | Spearman | 0.45 |
| colonias | `share_explicit`, `angry_share_mean` | Spearman | -0.46 |
| colonias | `centroid_lat`, `angry_share_mean` | Spearman | 0.32 |
| colonias | `settlement_type`, `log1p(n_posts)` | eta | 0.37 |
| ubicaciones | `location_type`, `match_method` | V de Cramér | 1.00 |
| ubicaciones | `source_field`, `has_image` | V de Cramér | 0.30 |
| ubicaciones | `n_colonias`, `spread_km` (por publicación) | Spearman | 0.82 |
| ubicaciones | `n_colonias`, `reactions_angry` (por publicación) | Spearman | 0.30 |

## Reducción de dimensión

| Dataset | Espacio | Filas × variables | Varianza PC1 + PC2 | Trustworthiness PCA | t-SNE | UMAP |
|---|---|---|---:|---:|---:|---:|
| publicaciones | Interacción y metadatos | 5,200 × 17 | 44% | 0.82 | 0.99 | 0.97 |
| publicaciones | Texto (TF-IDF + SVD 50) | 5,200 × 50 | | 0.72 | 0.99 | 0.98 |
| colonias | Área, centroide y menciones (ciudad) | 762 × 10 | 54% | 0.90 | 0.98 | 0.98 |
| ubicaciones | Huella territorial por publicación | 3,788 × 11 | 49% | 0.95 | 1.00 | 1.00 |

- Interacción: los grupos de t-SNE y UMAP los definen sobre todo las variables binarias de
  entrada; coloreados por `event_type` y por periodo (no son entrada) los colores se mezclan.
- Texto: `corte_programado` y `restablecimiento` forman islas; "otro" se divide en muchas islas.
- Colonias: las 206 colonias de la ciudad sin menciones forman un grupo aparte en los tres métodos.
- Ubicaciones: el número de colonias distintas ordena las tres proyecciones.

## Consulta con los usuarios

Público del tablero por definir (README). Preguntas registradas en la sección 7 de cada
notebook; estado: pendiente.

| Dataset | Pregunta | Estado |
|---|---|---|
| publicaciones | ¿Qué temas distinguir dentro de "otro" (75% de las publicaciones)? | Pendiente |
| publicaciones | ¿Ver publicaciones sueltas o episodios de varios días? | Pendiente |
| publicaciones | ¿La duración anunciada es un dato que buscan? | Pendiente |
| publicaciones | ¿`angry_share`, comentarios o texto de comentarios como medida de molestia? | Pendiente |
| publicaciones | ¿Eventos del 5 al 19 de abril de 2024 o agosto y septiembre de 2026 que recuperar? | Pendiente |
| colonias | ¿Por qué 221 colonias nunca aparecen y cómo mostrarlas? | Pendiente |
| colonias | "Centro" y "Solidaridad" sueltos: ¿colonia o zona? | Pendiente |
| colonias | ¿Agua de Hermosillo da servicio en Bahía de Kino y Miguel Alemán? | Pendiente |
| colonias | ¿Distinguir una colonia de su ampliación o privada? | Pendiente |
| colonias | ¿Coincide el mayor enojo en el norte con su experiencia? | Pendiente |
| ubicaciones | ¿Aceptar menciones por nombre suelto (74%) en el mapa? | Pendiente |
| ubicaciones | ¿Ponderar los avisos masivos (hasta 91 lugares)? | Pendiente |
| ubicaciones | ¿Ubicar cada cruce o basta la colonia? | Pendiente |
| ubicaciones | Cruces sobre bulevares: ¿una colonia o las dos de cada lado? | Pendiente |
| ubicaciones | ¿Qué mide mejor el impacto: colonias afectadas, duración o molestia? | Pendiente |
