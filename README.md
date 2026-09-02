# project_name

Descarga los datos del DENUE (directorio nacional de unidades económicas) del INEGI
para Sonora y los convierte en un dataset pequeño con ingeniería de características.
Está construido como un pipeline de jobs: descargar datos crudos, extraerlos y
transformarlos, y dejar el resultado en `data/processed/`.

## Instalación

```
cp params-example.yml params.yml
uv sync
```

`params.yml` (ignorado por git) declara las fuentes de datos: URLs y rutas
`raw`/`interim`/`processed`. `params-example.yml` es la plantilla versionada.

## Uso

```
make ingest   # descarga el zip crudo del DENUE a data/raw/
make process  # lo extrae y transforma hacia data/processed/
make test     # corre la suite de pruebas
make lint     # ruff check + format --check
make format   # ruff check --fix + format
```

## Estructura

```
params.yml                 <- configuración de fuentes de datos (ignorado por git; ver params-example.yml)
project_name/
├── config.py               <- carga params.yml, configura el logging
├── constants.py             <- rutas del directorio data/
├── features.py               <- transformaciones con pandas (columnas crudas del DENUE -> features)
├── logging.py                <- decorador @log_execution (inicio/fin/error + tiempo)
├── clients/                   <- cliente HTTP de descarga + un wrapper delgado para INEGI
├── policies/                   <- FilePolicy: skip/overwrite/error ante archivos existentes
└── jobs/
    ├── ingest_denue_sonora_job.py    <- descarga el zip crudo
    └── process_denue_sonora_job.py    <- zip crudo -> csv interim -> csv processed

notebooks/    
tests/       
data/         <- raw / interim / processed / external, según las rutas de params.yml
logs/         <- logs de los jobs (project_name.log)
```
