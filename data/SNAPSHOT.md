# Snapshot de `data/external`

`data/external/` contiene datos que **no se pueden regenerar** de forma confiable:

| Contenido | Cómo se generó | Por qué no es reproducible |
|---|---|---|
| `dataset_facebook-posts-scraper_*.csv` (5 rangos de fecha) | Scraper de Facebook en Apify | Servicio de paga; los posts cambian o se borran |
| `facebook/images/<csv>/` (imágenes + `manifest_*.csv`) | `make extract-images` | Las URLs de las imágenes expiran |
| `facebook/ocr/<csv>/ocr_*.csv` (+ `.meta.json`) | `make ocr` (PaddleOCR-VL-1.6) en Yuca/ACARUS | Depende de hardware y versiones; ver cada `.meta.json` |

Por eso el proyecto los trata como un insumo congelado: el archivo comprimido vive
en OneDrive (privado: son posts de Facebook y pueden tener datos personales) y en
git solo se versiona `data/external.sha256`, con el checksum de cada archivo.

## Versión actual

- **Versión:** v1 (`backups/external_snapshot_20260916.tar.gz`)
- **Ubicación:** OneDrive Unison — _pendiente: pegar aquí el enlace_
- **Acceso:** pedirlo al equipo; el enlace es solo para cuentas `@unison.mx`.

## Cómo usarlo

1. Descarga `external_snapshot_<fecha>.tar.gz` de OneDrive.
2. Desde la raíz del proyecto: `tar -xzf ruta/al/external_snapshot_<fecha>.tar.gz -C data/`
3. `make verify-data` debe terminar con
   `data/external coincide con data/external.sha256`.

## Cómo publicar una nueva versión

Solo si cambian los datos externos (p. ej. un nuevo rango de posts):

1. Correr la adquisición (`extract-images`, `ocr`; ver `README.md` y `slurm/README.md`).
2. `make snapshot` → reescribe `data/external.sha256` y crea el tar.gz en `backups/`.
3. Subir el tar.gz a OneDrive, actualizar la sección **Versión actual** y hacer commit de
   `data/external.sha256` y de este archivo juntos.
