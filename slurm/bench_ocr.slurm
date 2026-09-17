#!/bin/bash
# Benchmark (opcional): OCR de UNA imagen midiendo por separado la carga del
# modelo, la 1a pasada y la 2a pasada, para comparar hardware.
# Uso:
#   sbatch --export=ALL,IMAGE=data/external/.../foto.jpg slurm/bench_ocr.slurm
# En CPU (para comparar):
#   sbatch -p cpu --gres=none -c 64 --export=ALL,DEVICE=cpu,IMAGE=... slurm/bench_ocr.slurm
#SBATCH --job-name=bench-ocr
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
export DEVICE="${DEVICE:-gpu:0}"
: "${IMAGE:?Falta IMAGE. Uso: sbatch --export=ALL,IMAGE=ruta.jpg slurm/bench_ocr.slurm}"

echo "Nodo: $(hostname) | device: $DEVICE | imagen: $IMAGE"

uv run --no-sync python - <<'EOF'
import os, time
from pathlib import Path
from project_name.clients.ocr import OcrClient

t0 = time.perf_counter()
client = OcrClient(device=os.environ["DEVICE"])
t1 = time.perf_counter()
text = client.extract_text(Path(os.environ["IMAGE"]))
t2 = time.perf_counter()
client.extract_text(Path(os.environ["IMAGE"]))  # 2a pasada: ya "caliente"
t3 = time.perf_counter()

print(text)
print("-" * 60)
print(f"Carga del modelo:        {t1 - t0:6.1f} s")
print(f"OCR 1a pasada (fría):    {t2 - t1:6.1f} s")
print(f"OCR 2a pasada (caliente):{t3 - t2:6.1f} s")
EOF
