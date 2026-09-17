#!/bin/bash
# Prepara el entorno de Python en Yuca. Correr en el nodo de login (tiene
# internet), desde la raíz del proyecto:  bash slurm/setup_yuca.sh
# Es el mismo `make requirements-ocr` que en tu Mac, pero con TORCH=rocm (las
# GPUs de Yuca son AMD); la versión exacta sale de uv.lock.
set -euo pipefail

if ! command -v uv >/dev/null; then
    curl -LsSf https://astral.sh/uv/install.sh | sh
    export PATH="$HOME/.local/bin:$PATH"
fi

make requirements-ocr TORCH=rocm
mkdir -p logs/slurm

uv run --no-sync python -c "import torch; print('torch', torch.__version__, '| ROCm', torch.version.hip)"
