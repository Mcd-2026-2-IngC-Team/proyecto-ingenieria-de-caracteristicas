<a target="_blank" href="https://cookiecutter-data-science.drivendata.org/">
    <img src="https://img.shields.io/badge/CCDS-Project%20template-328F97?logo=cookiecutter" />
</a>

# Proyecto de ingeniería de características
## Tema y pregunta

Por definir. Hasta ahora el proyecto reúne datos sobre servicios urbanos en
Hermosillo: reportes de baches, colonias y calles, avisos de cortes y reparaciones
de agua y, próximamente, fugas.

Pregunta a contestar al final de los 3 proyectos: por definir.

## Público

Por definir: a quién va dirigido el tablero final.

## Fuentes primarias

- Bachómetro de Hermosillo: reportes ciudadanos de baches desde 2021.
  https://bachometro.hermosillo.gob.mx
- Página de Facebook de Agua de Hermosillo: avisos de cortes, reparaciones y
  restablecimientos, con el texto de sus volantes extraído por OCR (ver
  [data/SNAPSHOT.md](data/SNAPSHOT.md)).
- INEGI, Delimitación de colonias y otros asentamientos humanos (DCAH) 2025.
  https://www.inegi.org.mx/programas/dcah/
- INEGI, Marco Geoestadístico 2025, Sonora (calles). https://www.inegi.org.mx/temas/mg/
- Fugas de agua: próximamente.

## Reproducir

```
uv sync
# descarga el snapshot de data/external (ver data/SNAPSHOT.md) y descomprímelo en data/
make verify-data
make data
```

`make help` lista las demás reglas. Las fuentes y rutas se configuran en `params.yml`;
los diccionarios de datos están en [references/](references/README.md) y el OCR en el
cluster en [slurm/](slurm/README.md).
