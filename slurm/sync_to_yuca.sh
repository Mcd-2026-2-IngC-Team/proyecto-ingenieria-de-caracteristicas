#!/bin/bash
# Copia el proyecto (y opcionalmente los pesos del modelo) de tu Mac a Yuca.
# Uso, desde la raíz del proyecto en tu Mac:
#   bash slurm/sync_to_yuca.sh            # solo código + data/
#   bash slurm/sync_to_yuca.sh --models   # además ~/.paddlex/official_models (~2 GB, solo la 1a vez)
# Requiere el alias "yuca" en ~/.ssh/config (ver slurm/README.md).
set -euo pipefail

REMOTE="${YUCA_HOST:-yuca}"
REMOTE_DIR="${YUCA_DIR:-proyecto-ic}"

rsync -avz --progress \
    --exclude .venv --exclude .git --exclude __pycache__ \
    --exclude .pytest_cache --exclude .ruff_cache --exclude .DS_Store \
    --exclude backups --exclude logs \
    ./ "$REMOTE:$REMOTE_DIR/"

if [[ "${1:-}" == "--models" ]]; then
    ssh "$REMOTE" 'mkdir -p ~/.paddlex/official_models'
    rsync -avz --progress ~/.paddlex/official_models/ "$REMOTE:.paddlex/official_models/"
fi
