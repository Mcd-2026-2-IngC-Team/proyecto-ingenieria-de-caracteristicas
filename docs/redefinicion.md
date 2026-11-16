# Redefinición del tema y la pregunta

Corte: 15 de noviembre de 2026. Evidencia en `notebooks/08-exploracion-redefinicion.ipynb`
(fuente: `notebooks/marimo/08-exploracion-redefinicion.py`).

## Tema

- Emergencias urbanas ligadas a la lluvia en Hermosillo: inundaciones, árboles caídos,
  hundimientos, socavones y alcantarillas, según las llamadas al 911.
- La lluvia diaria es la variable explicativa; la red hidrográfica y las colonias del INEGI
  dan la ubicación; las publicaciones de Agua de Hermosillo dan el contexto de las
  afectaciones al suministro por tormentas.

## Pregunta

¿Cuánto aumentan las emergencias urbanas reportadas al 911 en Hermosillo cuando llueve, qué
tipos de incidente responden y en qué colonias se concentran en cada temporada de lluvias?

- Parte descriptiva: calendario de llamadas por tipo de incidente y mapa por colonia y
  temporada.
- Parte diagnóstica: respuesta del conteo diario a la lluvia, por tipo de incidente, con
  días secos de la misma temporada como control.

## Público

- Protección Civil municipal y el C5 de Hermosillo, para dimensionar la atención de
  emergencias en los días posteriores a una lluvia y ubicar las colonias afectadas en cada
  temporada.
- Secundario: periodistas y ciudadanía, con el calendario y el mapa de afectaciones.

## Fuentes

| Fuente | Contenido | Periodo | Archivo procesado |
|---|---|---|---|
| Llamadas al 911 (Hugging Face, Marcelinux) | 4,176 llamadas de 28 tipos ligados a agua y terreno, con colonia en texto | 2018-01 a 2025-09 | `data/processed/llamadas_911/llamadas_911_hermosillo.csv` |
| Open-Meteo, estimación de reanálisis (modelo no confirmado) | Precipitación diaria (mm) y horas con lluvia en el punto de la ciudad | 2018-01 a 2026-09 | `data/processed/precipitacion/precipitacion_hermosillo.csv` |
| INEGI DCAH 2025 | 762 colonias de la ciudad con polígono y clave | 2025 | `data/processed/aguah/colonias_hermosillo.gpkg` |
| INEGI Red Hidrográfica 1:50k | Tramos de cauce de cuatro subcuencas | 1998 a 2010 | `data/processed/inegi/hidrografia_hermosillo/subc_hermosillo.gpkg` |
| Agua de Hermosillo (Facebook) | 5,200 publicaciones con texto, OCR, tipo de evento y reacciones | 2020-12 a 2026-09 | `data/processed/aguah/publicaciones_aguah.csv` |
| Bachómetro | 39,018 reportes de baches con punto y descripción | 2021-09 a 2026-09 | `data/processed/bachometro/baches_hermosillo.csv` |

## Requisitos del curso

| Requisito | Cumplimiento |
|---|---|
| Series de tiempo | Llamadas al 911 y lluvia, diarias de 2018 a 2025 |
| Información georreferenciada | Colonia (clave del INEGI), centroide y distancia al cauce más cercano |
| Datos cualitativos | Tipo y grupo de incidente, tipo de asentamiento, tipo de evento de Agua de Hermosillo |
| Datos cuantitativos | Conteos diarios, mm de lluvia, distancia al cauce, reacciones |
| Texto | Publicaciones y OCR de Agua de Hermosillo; descripciones de baches |
| Dos fuentes o más | 911, Open-Meteo, INEGI, Agua de Hermosillo, Bachómetro |
| Público | Protección Civil municipal y C5; periodistas y ciudadanía |

## Resultado de cada exploración

| Id | Pregunta | Resultado | Decisión |
|---|---|---|---|
| E8 | Cobertura | Ventana común de 911 y lluvia: 2018-01 a 2025-09; 67% de llamadas con colonia única por nombre | Limitación declarada |
| E1 | Calendario | 911 terreno: 57% a 74% del año en julio a septiembre, 7 de 7 años; baches: 24% a 27% | Se conserva para 911 |
| E2 | Respuesta a la lluvia | 911 inundación 21.7 veces, terreno 3.7, drenaje 2.5; baches 0.97 dentro del mismo mes; emergencias de Agua de Hermosillo 0.99 | Hallazgo principal |
| E3 | Temporada seca | Abril a junio concentra emergencias solo en 2023 (48.5%); 28 de 41 publicaciones de pipas en julio y agosto de 2024 | Se descarta como temporada |
| E4 | Colonias y cauces | Mediana de distancia al cauce: inundación 357 m, terreno 519 m; Spearman por colonia 0.03; persistencia entre años 0.01 a 0.23 | Solo descriptivo |
| E5 | Anomalías | 36 días con 2 votos o más: 83% en julio a septiembre, 92% con lluvia previa de 1 mm o más, 36% con 10 mm o más | Validación y límite del reanálisis |
| E6 | Perfiles de colonia | PC1 (33%) contrasta julio con agosto; Spearman con distancia al cauce −0.17 | Apoyo de E4 |
| E7 | Texto | Lluvia en 0.5% a 1.5% de las descripciones de baches; en 7% de publicaciones de Agua de Hermosillo en julio y agosto | Evidencia cualitativa |

## Lo que se consolida y lo que se desecha de los EDA previos

| Elemento | Origen | Decisión |
|---|---|---|
| Estacionalidad del 911 por grupo | `notebooks/AAMM/07` | Se consolida; el notebook dice agosto a octubre y el código usa julio a septiembre |
| Distancia al cauce por grupo de incidente | `notebooks/AAMM/07` | Se consolida; reproducida en E4 (357 m contra 519 m) |
| Cruce espacial de baches a colonia | `project_name/jobs/add_colonia_bache_with_gpkg.py` | Se conserva para el tablero; los baches salen de la pregunta |
| Salto de julio a agosto en baches | `docs/cinco_v_datos.md` | Se desecha como señal de lluvia: julio es el mes más bajo |
| Hipótesis de lluvia para emergencias de Agua de Hermosillo | `notebooks/AAMM/06` | Se desecha: razón 0.99 |
| Episodios de interacción en Agua de Hermosillo | `notebooks/05`, celda 27 | Contexto para etiquetar eventos en el tablero |
| Sectores Norte, Centro y Sur | `notebooks/AAMM/05` | Solo agrupador; la etiqueta de latitud (27.3 N) es errónea |
| Correlaciones por construcción (`likes_count` con `reactions_total`, `n_posts` con `n_mentions`, `ORDER_1` con `ARBSUM_1`) | notebooks 05 a 07, AAMM 06 y 09 | Se desechan |
| t-SNE y UMAP de interacción y de huella | notebooks 05 y 07 | Se desechan: los grupos los define la codificación de entrada |
| Tasa por clase de cercanía | `notebooks/AAMM/08`, celda 25 | Se desecha: divide entre el área de todo el sector |
| K-Means sobre distancias | `notebooks/AAMM/08` y `09` | Se desecha: distancias colineales; el grupo repite el sector |
| Kruskal-Wallis sobre llamadas | `notebooks/AAMM/07` | Se desecha: filas no independientes |
| Cruce de baches por nombre de colonia | `project_name/jobs/add_colonia_name_to_bache_job.py` | Se desecha: salida 100% nula |
| Tukey sobre `top_comment_likes` | `notebooks/05` | Se desecha: 66% de ceros |

## Cambios al pipeline

- Fuente nueva: `project_name/jobs/ingest_precipitacion_job.py` y
  `project_name/jobs/process_precipitacion_job.py`, configurados en `params.yml`
  (`sources.open_meteo`), dentro de `make download` y `make data`; pruebas en
  `tests/test_precipitacion_jobs.py`.
- `params.yml`: el procesado de baches apunta a `baches_hermosillo.csv`, el archivo que leen
  los jobs siguientes; antes apuntaba a `baches_hermosillo_colonia_filled.csv`, que ningún
  job lee.
- `project_name/water_events.py`: cargas y cálculos compartidos por el notebook 08 y
  `scripts/figura_hallazgo.py`.
