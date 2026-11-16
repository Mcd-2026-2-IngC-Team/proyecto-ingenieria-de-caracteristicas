<a target="_blank" href="https://cookiecutter-data-science.drivendata.org/">
    <img src="https://img.shields.io/badge/CCDS-Project%20template-328F97?logo=cookiecutter" />
</a>
<a target="_blank" href="https://github.com/Mcd-2026-2-IngC-Team/proyecto-ingenieria-de-caracteristicas/actions/workflows/ci.yml">
    <img src="https://github.com/Mcd-2026-2-IngC-Team/proyecto-ingenieria-de-caracteristicas/actions/workflows/ci.yml/badge.svg" />
</a>

# Proyecto de ingeniería de características
## Tema y pregunta

Tema: emergencias urbanas ligadas a la lluvia en Hermosillo (inundaciones, árboles
caídos, hundimientos, socavones y alcantarillas) según las llamadas al 911, con la lluvia
diaria como variable explicativa, las colonias y la red hidrográfica del INEGI como
ubicación, y las publicaciones de Agua de Hermosillo como contexto.

Pregunta a contestar al final de los 3 proyectos: ¿cuánto aumentan las emergencias
urbanas reportadas al 911 en Hermosillo cuando llueve, qué tipos de incidente responden y
en qué colonias se concentran en cada temporada de lluvias?

Evidencia y criterios: [docs/redefinicion.md](docs/redefinicion.md). Hallazgos:
[docs/reporte_hallazgos.md](docs/reporte_hallazgos.md).

## Público

Protección Civil municipal y el C5 de Hermosillo; en segundo lugar, periodistas y
ciudadanía.

## Fuentes primarias

- Bachómetro de Hermosillo: reportes ciudadanos de baches desde 2021.
  https://bachometro.hermosillo.gob.mx
- Página de Facebook de Agua de Hermosillo: avisos de cortes, reparaciones y
  restablecimientos, con el texto de sus volantes extraído por OCR (ver
  [data/SNAPSHOT.md](data/SNAPSHOT.md)).
- INEGI, Delimitación de colonias y otros asentamientos humanos (DCAH) 2025.
  https://www.inegi.org.mx/programas/dcah/
- INEGI, Marco Geoestadístico 2025, Sonora (calles). https://www.inegi.org.mx/temas/mg/
- INEGI, Red Hidrográfica escala 1:50 000, edición 2.0: información de la red hidrográfica y subcuencas de Hermosillo. https://www.inegi.org.mx/temas/hidrografia/#mapas
- Llamadas al 911 por colonia, Hermosillo 2018 a 2025 (Hugging Face, Marcelinux, CC-BY-4.0).
  https://huggingface.co/datasets/Marcelinux/llamadas911_colonias_hermosillo_2018_2025
- Open-Meteo, API de archivo histórico: precipitación diaria 2018 a 2026 (CC-BY-4.0).
  https://open-meteo.com/en/docs/historical-weather-api

[docs/cinco_v_datos.md](docs/cinco_v_datos.md) resume estas fuentes y los datos procesados
con el marco de las cinco V (volumen, velocidad, variedad, veracidad y valor).

## Análisis exploratorio

Un notebook por dataset tidy, con auto EDA, faltantes, anomalías, relaciones, correlación,
reducción de dimensión y preguntas para los usuarios:

- [05, publicaciones de Agua de Hermosillo](notebooks/05-eda-publicaciones-aguah.ipynb)
- [06, colonias de Hermosillo](notebooks/06-eda-colonias-hermosillo.ipynb)
- [07, ubicaciones mencionadas en los avisos](notebooks/07-eda-ubicaciones-aviso.ipynb)
- [08, exploración para redefinir la pregunta](notebooks/08-exploracion-redefinicion.ipynb):
  cruza lluvia, 911, baches y Agua de Hermosillo en el tiempo

Los reportes de ydata-profiling están en [docs/eda/](docs/eda/) (`make profile`) y el
resumen de hallazgos en [docs/eda.md](docs/eda.md).

## Reproducir

Consultar [data/SNAPSHOT.md](data/SNAPSHOT.md) antes de ejecutar el proyecto.

```
uv sync
# descarga el snapshot de data/external (ver data/SNAPSHOT.md) y descomprímelo en data/
make verify-data
make data
```

`make data` termina revisando `data/processed/` con las reglas de calidad de
[project_name/schemas.py](project_name/schemas.py) (Pandera: llaves únicas, rangos,
catálogos y coordenadas); `make validate` corre solo esa revisión.

`make help` lista las demás reglas. Las fuentes y rutas se configuran en `params.yml`;
los diccionarios de datos están en [references/](references/README.md) y el OCR en el
cluster en [slurm/](slurm/README.md).

```
project_name.jobs.neighborhood_baches_info_job 
# subconsulta que obtiene la colina asignada al id del bache

uv run python -m project_name.jobs.add_colonia_name_to_bache_job
# Agrega las colonias al csv de baches_hermosillo
```
