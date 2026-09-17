#!/bin/bash
# Verifica que torch ve la GPU AMD del nodo y si el nodo tiene internet.
# Uso: sbatch slurm/check_gpu.slurm   ->  resultado en logs/slurm/check-gpu-<jobid>.out
#SBATCH --job-name=check-gpu
#SBATCH --account=curso06
#SBATCH --partition=gpu
#SBATCH --gres=gpu:1
#SBATCH --cpus-per-task=2
#SBATCH --mem=4G
#SBATCH --time=00:05:00
#SBATCH --output=logs/slurm/%x-%j.out

echo "Nodo: $(hostname)"
env | grep -E 'VISIBLE_DEVICES' || true
rocm-smi 2>/dev/null || echo "(rocm-smi no está en el PATH; prueba 'module avail rocm')"

.venv/bin/python - <<'EOF'
import torch
print("torch", torch.__version__, "| ROCm", torch.version.hip)
print("GPU disponible:", torch.cuda.is_available())
if torch.cuda.is_available():
    print("GPU:", torch.cuda.get_device_name(0))
    print("Memoria GPU (GB):", round(torch.cuda.get_device_properties(0).total_memory / 1e9, 1))
    x = torch.randn(2000, 2000, device="cuda")
    print("bfloat16 soportado:", torch.cuda.is_bf16_supported())
    print("matmul OK:", (x @ x).sum().item())
EOF

curl -sS -m 5 -o /dev/null -w "Internet: HTTP %{http_code}\n" https://huggingface.co || echo "Internet: NO"
