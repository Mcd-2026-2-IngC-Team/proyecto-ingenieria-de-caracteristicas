#!/bin/bash
# OCR de UNA imagen (el mismo `make ocr-image` que en tu Mac), para probar rápido.
# Uso:
#   sbatch --export=ALL,IMAGE=data/external/.../foto.jpg slurm/ocr_image.slurm
#SBATCH --job-name=ocr-image
#SBATCH --account=curso06
#SBATCH --partition=gpu
#SBATCH --gres=gpu:1
#SBATCH --cpus-per-task=8
#SBATCH --mem=32G
#SBATCH --time=00:30:00
#SBATCH --output=logs/slurm/%x-%j.out

set -euo pipefail
export PATH="$HOME/.local/bin:$PATH"
export OMP_NUM_THREADS="$SLURM_CPUS_PER_TASK"
# Los nodos de cómputo no tienen internet: el entorno ya lo instaló
# setup_yuca.sh en el login y los pesos ya están en ~/.paddlex.
export UV_OFFLINE=1
export PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK=True
export HF_HUB_OFFLINE=1

: "${IMAGE:?Falta IMAGE. Uso: sbatch --export=ALL,IMAGE=ruta.jpg slurm/ocr_image.slurm}"

echo "Nodo: $(hostname) | imagen: $IMAGE"
make ocr-image TORCH=rocm DEVICE="${DEVICE:-gpu:0}" IMAGE="$IMAGE"
