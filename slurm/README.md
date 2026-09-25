# Correr el OCR en Yuca (ACARUS)

El OCR es parte de la **adquisición** (no reproducible; ver `data/SNAPSHOT.md`).
Estos scripts solo *lanzan* en SLURM el mismo `make ocr` que corre en tu Mac,
con `TORCH=rocm` porque las GPUs de Yuca son AMD.

## Adquisición: imágenes y OCR

Estas reglas generaron `data/external/` y no se espera volver a correrlas; sus
opciones están en `make help`.

- `make extract-images` descarga las imágenes a las que apunta una columna de un CSV
  (por defecto, el CSV de Facebook y `media/0/photo_image/uri`). Cada CSV deja sus
  imágenes en `DEST/<nombre-del-csv>/` con un `manifest_<columna>.csv` que liga cada
  fila (por `ID_COLUMN`) con su archivo, o con el motivo por el que se omitió o falló.
  Las URLs vencidas se registran y no detienen la descarga.
- `make ocr MANIFEST=...` corre el pipeline completo de PaddleOCR-VL (layout y luego
  VLM por región) sobre las imágenes de un manifest: usar solo el VLM sobre la imagen
  completa alucina texto. Escribe `ocr_<columna>.csv` (texto por `id`) y
  `ocr_<columna>.meta.json` (fecha, máquina, device, job de SLURM, commit y versiones)
  en `data/external/facebook/ocr/<nombre-del-csv>/`.
- `make ocr-image IMAGE=...` corre el mismo pipeline sobre una imagen e imprime el
  texto, sin escribir nada.
- `TORCH` elige de dónde viene PyTorch (versiones fijadas en `uv.lock`): `cpu`
  (default, PyPI; Mac y Linux con CPU o NVIDIA) o `rocm` (GPUs AMD, como las de Yuca).
  `DEVICE` sobreescribe `ocr.device` de `params.yml`; `auto` usa `cpu`, que es lo que
  recomienda PaddleOCR en Apple Silicon porque la etapa de layout no soporta Metal/MPS.

## 0. Cómo funciona un cluster (lo mínimo)

- Al conectarte por `ssh` entras al **nodo de login**. Sirve para copiar archivos,
  instalar paquetes y **mandar trabajos**. No corras el OCR ahí: es compartido y
  no tiene GPU.
- Los cálculos corren en los **nodos de cómputo** y los reparte **SLURM** (la cola).
  Tú le pides recursos (GPU, CPUs, RAM, tiempo) y SLURM corre tu script cuando
  hay lugar.
- Yuca tiene 24 nodos de CPU (partición `cpu`, 64 núcleos y 1 TB RAM c/u) y 6 nodos de GPU
  (partición `gpu`, 48 núcleos) con **2 GPUs AMD
  MI210 c/u**. Son AMD, no NVIDIA: PyTorch necesita la build de **ROCm**.
- Todo trabajo lleva `--account=curso06`.
- `$HOME` tiene 100 GB. `/lustre/cursos/curso06` se comparte con el equipo.
  **Al final del semestre se borra todo**: respalda los resultados.

Comandos de SLURM que vas a usar:

| Comando | Qué hace |
|---|---|
| `sinfo` | Lista particiones (colas) y nodos |
| `sbatch script.slurm` | Manda un trabajo a la cola, te regresa un JOBID |
| `squeue -u $USER` | Tus trabajos (PD = en espera, R = corriendo) |
| `scancel JOBID` | Cancela un trabajo |
| `sacct -j JOBID --format=JobID,Elapsed,State,MaxRSS` | Cuánto tardó y cuánta RAM usó |
| `srun ... --pty bash` | Sesión interactiva dentro de un nodo de cómputo |

## 1. Conexión cómoda desde tu Mac (una sola vez)

Agrega esto a `~/.ssh/config` en tu Mac (cambia `TU_USUARIO`, p. ej. `estudiante_103`):

```
Host yuca
    HostName yuca.unison.mx
    User TU_USUARIO
    ControlMaster auto
    ControlPath ~/.ssh/cm-%r@%h:%p
    ControlPersist 4h
    ServerAliveInterval 60
```

Con esto `ssh yuca` pide contraseña y código de Google Authenticator una vez, y
durante 4 horas las demás conexiones (`rsync`, otra terminal) reutilizan esa sesión
sin volver a pedirlos.

## 2. Subir el proyecto y los pesos del modelo

Desde la raíz del proyecto en tu Mac:

```bash
bash slurm/sync_to_yuca.sh --models
```

Copia el código y `data/` a `~/proyecto-ic` en Yuca, y los pesos del modelo
(`~/.paddlex/official_models`, ~2 GB) para no descargarlos otra vez. Si después
solo cambias código, corre el script sin `--models`.

> Se usa `rsync` y no `git clone` porque tu rama tiene cambios sin commit y
> porque `data/` no está en git.

## 3. Preparar el entorno en Yuca (una sola vez)

```bash
ssh yuca
cd ~/proyecto-ic
bash slurm/setup_yuca.sh   # instala uv si falta y corre `make requirements-ocr TORCH=rocm`
```

Se corre en el login porque ahí sí hay internet. Vuelve a correrlo cada vez que
cambie `uv.lock`. Las particiones son `gpu` (2 × MI210 por nodo) y `cpu`
(`sinfo -o "%P %G %N"`).

En Yuca usa siempre `TORCH=rocm` (los `.slurm` ya lo hacen). Un `make ocr` con el
default `TORCH=cpu` cambiaría torch por la versión de PyPI.

## 4. Verificar la GPU

```bash
sbatch slurm/check_gpu.slurm
squeue -u $USER                  # espera a que desaparezca
cat logs/slurm/check-gpu-*.out
```

Debe decir `GPU disponible: True`. También te dice si los nodos tienen internet
y si la GPU soporta bfloat16.

Resultado real (2026-09-16): `AMD Instinct MI210`, ~64 GB, bfloat16 sí. Los nodos
de cómputo **no tienen internet** (falla SSL), por eso los modelos se copian a
`~/.paddlex` y los jobs usan `HF_HUB_OFFLINE=1`. `misproyectos` solo muestra
`curso06`, que es el valor de `--account`.

Si sale `False`: la versión de ROCm de torch no coincide con la del cluster
(`module avail rocm`). Cambia la URL de `[[tool.uv.index]] pytorch-rocm` en
`pyproject.toml` (hoy `rocm7.2`), corre `uv lock` en tu Mac, sincroniza y vuelve
a correr `setup_yuca.sh`.

## 5. Probar una imagen y comparar tiempos

Prueba rápida (`make ocr-image` en un nodo con GPU):

```bash
sbatch --export=ALL,IMAGE=data/external/facebook/images/dataset_facebook-posts-scraper_2025-01-01-to-2025-06-02/1070876551751282_media-0-photo_image-uri.jpg slurm/ocr_image.slurm
```

Benchmark opcional (`slurm/bench_ocr.slurm`, mismas variables). Su salida separa **carga del modelo**, **OCR en frío** y **OCR en caliente**.
Esto importa porque en tu Mac `make ocr-image` también mide `uv sync` y la carga
del modelo, no solo el OCR. Con muchas imágenes, el modelo se carga una sola vez,
así que lo que más pesa es el tiempo **en caliente** por imagen.

Para comparar contra CPU (nodos de 64 núcleos):

```bash
sbatch -p cpu --gres=none -c 64 --export=ALL,DEVICE=cpu,IMAGE=... slurm/bench_ocr.slurm
```

La primera pasada en GPU AMD es lenta porque ROCm compila kernels la primera vez.
Medido con la imagen de ejemplo (volante de AquaHermosillo):

| Etapa | Yuca, GPU MI210 | Mac M4, CPU |
|---|---|---|
| Carga del modelo | 46.7 s | 6.4 s |
| OCR 1a pasada (fría) | 55.1 s | 80.2 s |
| OCR 2a pasada (caliente) | **5.9 s** | 85.2 s |

En Yuca la GPU es ~14× más rápida por imagen; la carga es más lenta porque
`$HOME` está en Lustre (disco de red). Un manifest de 419 imágenes tardó
10 min 16 s en Yuca.

Por eso Yuca conviene para lotes (`ocr_manifest.slurm`) y no para una imagen suelta.

## 6. Correr un manifest completo

```bash
sbatch --export=ALL,MANIFEST=data/external/facebook/images/dataset_facebook-posts-scraper_2025-01-01-to-2025-06-02/manifest_media-0-photo_image-uri.csv slurm/ocr_manifest.slurm
tail -f logs/slurm/ocr-manifest-JOBID.out
```

Puedes mandar los 5 manifests a la vez: cada uno ocupa una GPU (la cuota es 4
GPUs, así que el quinto espera en la cola). Cada CSV sale con su `.meta.json`
(nodo, job de SLURM, commit y versiones).

## 7. Traer los resultados a tu Mac

```bash
rsync -avz yuca:proyecto-ic/data/external/facebook/ocr/ data/external/facebook/ocr/
```

Si los datos externos cambiaron, congélalos con `make snapshot` (ver `data/SNAPSHOT.md`).

## Sesión interactiva (para depurar)

```bash
srun -A curso06 -p gpu --gres=gpu:1 -c 8 --mem=32G -t 01:00:00 --pty bash
cd ~/proyecto-ic && UV_OFFLINE=1 make ocr-image TORCH=rocm DEVICE=gpu:0 IMAGE=RUTA.jpg
exit   # libera la GPU al terminar
```

## Si algo falla

- **Trabajo en `PD` mucho tiempo:** `squeue -u $USER` muestra el motivo en `NODELIST(REASON)`.
- **No encuentra el modelo o intenta descargarlo:** confirma que existe
  `~/.paddlex/official_models/PaddleOCR-VL-1.6` en Yuca.
- **Se queda sin memoria (OOM):** sube `--mem`, o si es la GPU, revisa la memoria
  que reportó `check_gpu.slurm`.
- **Soporte de ACARUS:** equipo_acarus@unison.mx
