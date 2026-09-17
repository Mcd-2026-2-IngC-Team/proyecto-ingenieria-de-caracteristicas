#!/bin/bash
# OCR de todas las imágenes de un manifest: el mismo `make ocr` que en tu Mac,
# pero con torch ROCm y la GPU del nodo.
# Uso:
#   sbatch --export=ALL,MANIFEST=data/external/facebook/images/<carpeta>/manifest_media-0-photo_image-uri.csv slurm/ocr_manifest.slurm
# Resultado: data/external/facebook/ocr/<carpeta>/ocr_media-0-photo_image-uri.csv (+ .meta.json)
#SBATCH --job-name=ocr-manifest
#SBATCH --account=curso06
#SBATCH --partition=gpu
#SBATCH --gres=gpu:1
#SBATCH --cpus-per-task=8
#SBATCH --mem=32G
#SBATCH --time=12:00:00
#SBATCH --output=logs/slurm/%x-%j.out

set -euo pipefail
export PATH="$HOME/.local/bin:$PATH"
export OMP_NUM_THREADS="$SLURM_CPUS_PER_TASK"
# Los nodos de cómputo no tienen internet: el entorno ya lo instaló
# setup_yuca.sh en el login y los pesos ya están en ~/.paddlex.
export UV_OFFLINE=1
export PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK=True
export HF_HUB_OFFLINE=1

: "${MANIFEST:?Falta MANIFEST. Uso: sbatch --export=ALL,MANIFEST=ruta.csv slurm/ocr_manifest.slurm}"

echo "Nodo: $(hostname) | manifest: $MANIFEST | inicio: $(date)"
make ocr TORCH=rocm DEVICE="${DEVICE:-gpu:0}" MANIFEST="$MANIFEST"
echo "Fin: $(date)"
