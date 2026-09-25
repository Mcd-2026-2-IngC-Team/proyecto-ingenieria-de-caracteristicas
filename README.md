# project_name

Pipeline de jobs que descarga datos crudos, los extrae y transforma, y deja el
resultado en `data/processed/`.

## Instalación

```
cp params-example.yml params.yml
uv sync
```

`params.yml` (ignorado por git) declara las fuentes de datos: URLs y rutas
`raw`/`interim`/`processed`. `params-example.yml` es la plantilla versionada.

## Uso

El proyecto tiene dos partes:

1. **Pipeline reproducible**: cualquiera lo puede correr en cualquier máquina.
2. **Adquisición de datos externos**: ya se ejecutó y no es reproducible. Sus
   resultados se congelaron en un snapshot (ver [`data/SNAPSHOT.md`](data/SNAPSHOT.md)).

### Pipeline reproducible

```
make data            # todo el pipeline: descarga las fuentes (make download) y genera data/processed/
make verify-data     # confirma que data/external es idéntico al snapshot (checksums en git)
make download        # descarga todas las fuentes crudas en paralelo (colonias, calles y baches)
make dictionary      # regenera los diccionarios de datos en references/ desde data/processed/
make test            # corre la suite de pruebas
make lint            # ruff check + format --check
make format          # ruff check --fix + format
```

Antes de `make verify-data`, descarga el snapshot de OneDrive y descomprímelo en
`data/` (instrucciones en `data/SNAPSHOT.md`).

Cada job de descarga deja, junto a sus archivos en `data/raw/`, un `FUENTE.txt` con
la institución, la URL de descarga, una descripción de qué contienen los datos, enlaces
a su documentación, la licencia y, por archivo, su tamaño, fecha de descarga y sha256.
La descripción y los enlaces de cada fuente se declaran en `params.yml`
(`description` y `documentation`). La fecha de descarga es la fecha de modificación
del archivo: si la política `skip` omite una descarga ya hecha, la fecha original se
conserva.

`make dictionary` perfila cada dataset de `data/processed/` con pandas (dtype, nulos,
valores distintos y rango) y escribe su diccionario de datos en
[`references/`](references/README.md): un CSV por
dataset (para que GitHub lo renderice como tabla) y su JSON equivalente en
`references/json/`. Las descripciones de columnas viven a mano en
`project_name/metadata/dictionary.py`, que falla si una columna no está descrita o si
sobra una descripción de una columna que ya no existe.

### Adquisición (ya ejecutada, no reproducible)

Estas reglas documentan cómo se generó `data/external/`. No se espera que
cualquiera pueda volver a correrlas: los posts vienen de un scraper de paga
(Apify), las URLs de las imágenes expiran y el OCR depende del hardware.

```
make extract-images  # descarga imágenes referenciadas en una columna de un CSV
make ocr             # corre OCR sobre las imágenes de un manifest
make snapshot        # congela data/external: data/external.sha256 + tar.gz en backups/
```

`make extract-images` recibe `SOURCE`, `DEST`, `COLUMN` e `ID_COLUMN` (todos
sobreescribibles, ej. `make extract-images SOURCE=... DEST=... COLUMN=...`).
Por defecto apunta al CSV de Facebook en `data/external/` y a la columna
`media/0/photo_image/uri`. Las imágenes de cada CSV quedan en su propia
subcarpeta (`DEST/<nombre-del-csv>/`), junto con un `manifest_<columna>.csv`
que liga cada fila del CSV (por `ID_COLUMN`) con el archivo descargado o el
motivo por el que se omitió/falló — útil para correr esto contra varios CSV
de distintos rangos de fecha sin que se pisen entre sí, y para que un job de
OCR posterior sepa qué imagen corresponde a qué fila. Las URLs vencidas o que
fallan se registran y se omiten; no detienen el resto de la descarga.

`make ocr` recibe `MANIFEST` (ruta a un `manifest_<columna>.csv` generado por
`make extract-images`) y corre el pipeline completo de PaddleOCR-VL (detección
de layout + reconocimiento VLM por región — usar solo el VLM sobre la imagen
completa produce texto alucinado, según la documentación oficial y confirmado
en pruebas) sobre cada imagen descargada. Escribe `ocr_<columna>.csv` con el
texto extraído por `id` (listo para unirse luego al CSV de posts) en
`data/external/facebook/ocr/<nombre-del-csv>/` (`ocr.output_dir` en
`params.yml`, o `--output-dir`), junto con `ocr_<columna>.meta.json`: fecha,
máquina, device, job de SLURM, commit y versiones de paquetes con que se generó.

Las dependencias pesadas de ML se instalan con `make requirements-ocr`
(`uv sync --extra ocr --extra $(TORCH)`); el resto del proyecto no las necesita.
`TORCH` elige de dónde viene PyTorch, con versiones fijadas en `uv.lock`:

- `TORCH=cpu` (default): PyPI; Mac y Linux con CPU o NVIDIA.
- `TORCH=rocm`: build ROCm para GPUs AMD, como las de Yuca (ACARUS). Para correr
  ahí con SLURM, ver [`slurm/README.md`](slurm/README.md).

`DEVICE` sobreescribe `ocr.device` de `params.yml` (por defecto `auto` → `cpu`,
que es lo que PaddleOCR recomienda en Apple Silicon, ya que la etapa de layout
no tiene soporte Metal/MPS). Ejemplo: `make ocr TORCH=rocm DEVICE=gpu:0 MANIFEST=...`.

`make ocr-image IMAGE=ruta/a/una/imagen.jpg` corre el mismo pipeline sobre una
sola imagen e imprime el texto extraído en la terminal, sin escribir ningún
CSV — útil para probar rápido antes de correr `make ocr` contra un manifest
completo.

`make process-baches` script que junta todos los json obtenidos por la consulta a bachómetro hermosillo
en un solo csv

## Estructura

```
params.yml                 <- configuración de fuentes de datos (ignorado por git; ver params-example.yml)
project_name/
├── config.py               <- carga params.yml, configura el logging
├── constants.py             <- rutas del directorio data/
├── logging.py                <- decorador @log_execution (inicio/fin/error + tiempo)
├── metadata/                  <- documentación de los datos: origen (source) y columnas (dictionary)
│   ├── source.py                <- sha256 y FUENTE.txt: descripción, enlaces y fecha de descarga de cada fuente cruda
│   └── dictionary.py             <- diccionarios de datos en references/ (make dictionary)
├── clients/                   <- cliente HTTP de descarga, cliente OCR (pipeline PaddleOCR-VL: layout + VLM) + wrapper delgado para INEGI
├── policies/                   <- FilePolicy: skip/overwrite/error ante archivos existentes
└── jobs/
    ├── download_job.py                <- corre en paralelo todas las ingestas de abajo (make download)
    ├── ingest_baches_job.py           <- Obtiene la información de bachómetro de hermosillo desde el año 2021 a la fecha actual
    ├── ingest_dcah_job.py             <- descarga solo Sonora del paquete nacional de colonias (DCAH), por rango
    ├── ingest_mg_streets_job.py       <- descarga solo la capa de calles (26e) del Marco Geoestadístico, por rango
    ├── process_baches_sonora_job.py   <- jsons por año de bachometro -> csv integrado 
    ├── extract_images_job.py          <- descarga imágenes desde una columna de un CSV (--source/--dest/--column/--id-column)
    ├── ocr_images_job.py              <- corre OCR sobre un manifest o una sola imagen (--manifest | --image, --device, --output-dir)
    └── snapshot_external_job.py       <- congela (--write) o verifica (--verify) data/external contra data/external.sha256

notebooks/
├── marimo/     <- código fuente editable (make nb NOTEBOOK=<nombre>)
└── *.ipynb     <- export con outputs, se renderiza en GitHub
tests/       
data/         <- raw / interim / processed / external, según las rutas de params.yml
              <- SNAPSHOT.md + external.sha256: de dónde sale data/external y cómo verificarlo
references/   <- diccionarios de datos generados por make dictionary (ver references/README.md)
slurm/        <- lanzadores para correr la adquisición (OCR) en el cluster Yuca con SLURM
logs/         <- logs de los jobs (project_name.log)
```
