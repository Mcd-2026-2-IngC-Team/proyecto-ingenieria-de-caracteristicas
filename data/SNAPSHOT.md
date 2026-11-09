# Snapshot de `data/external`

`data/external/` contiene datos que **no se pueden regenerar** de forma confiable:

| Contenido | Cómo se generó | Por qué no es reproducible |
|---|---|---|
| `dataset_facebook-posts-scraper_*.csv` (5 rangos de fecha) | Scraper de Facebook en Apify | Servicio de paga; los posts cambian o se borran |
| `facebook/images/<csv>/` (imágenes + `manifest_*.csv`) | `make extract-images` | Las URLs de las imágenes expiran |
| `facebook/ocr/<csv>/ocr_*.csv` (+ `.meta.json`) | `make ocr` (PaddleOCR-VL-1.6) en Yuca/ACARUS | Depende de hardware y versiones; ver cada `.meta.json` |
| `distritos_sectores_hermosillo_PDU_2025.csv` | Transcripción manual de la Tabla III.1 del PDU de Hermosillo 2025+ (sectores y distritos con sus colonias) | El original es un PDF oficial; el CSV se transcribió a mano |

Por eso el proyecto los trata como un insumo congelado: el archivo comprimido vive
en OneDrive (privado: son posts de Facebook y pueden tener datos personales) y en
git solo se versionan los checksums `data/external.sha256` (snapshot de Facebook)
y `data/external_PDU.sha256` (CSV del PDU), para verificar que los datos son
exactamente los mismos.

## Versión actual

- **Versión:** v1 (`backups/external_snapshot_20260916.tar.gz`)
- **Ubicación:** OneDrive Unison — https://unisonmx-my.sharepoint.com/:f:/g/personal/a220212781_unison_mx/IgBKPXlOdPheQZloCQRezUxXAeNe98Njfu9Bdp2gJqaox7w?e=15hiHH 
- **Acceso:** pedirlo al equipo; el enlace es solo para cuentas `@unison.mx`.

## Cómo usarlo

1. Descarga `external_snapshot_<fecha>.tar.gz` de OneDrive.
2. Desde la raíz del proyecto: `tar -xzf ruta/al/external_snapshot_<fecha>.tar.gz -C data/`
3. `make verify-data` debe terminar con
   `data/external coincide con data/external.sha256` y
   `data/external (PDU) coincide con data/external_PDU.sha256`.

## CSV de sectores del PDU

El `external_snapshot_*.tar.gz` **no** incluye `distritos_sectores_hermosillo_PDU_2025.csv`:
es otra fuente externa que se descarga por separado.

- **Ubicación:** SharePoint Unison (carpeta `public-data-ing-2026`) —
  https://unisonmx-my.sharepoint.com/:f:/r/personal/a226230014_unison_mx/_layouts/15/onedrive.aspx?id=%2Fpersonal%2Fa226230014%5Funison%5Fmx%2FDocuments%2F1er%20Semestre%2FIng%2E%20Caracter%C3%ADsticas%2Fpublic%2Ddata%2Ding%2D2026&share=cgpZe0YOjR6YQKQF3FvXhosUEgUBSeFfgx3rQCxduezmOz%2D0PQ
- **Acceso:** pedirlo al equipo (cuentas `@unison.mx`).

Pasos:

1. Descarga `distritos_sectores_hermosillo_PDU_2025.csv` del enlace.
2. Colócalo en `data/external/`.
3. `make verify-data` debe terminar con
   `data/external (PDU) coincide con data/external_PDU.sha256`.

## Cómo publicar una nueva versión

Solo si cambian los datos externos (p. ej. un nuevo rango de posts):

1. Correr la adquisición (`extract-images`, `ocr`; ver `slurm/README.md`).
2. `make snapshot` → reescribe `data/external.sha256` y crea el tar.gz en `backups/`.
3. Subir el tar.gz a OneDrive, actualizar la sección **Versión actual** y hacer commit de
   `data/external.sha256` y de este archivo juntos.
