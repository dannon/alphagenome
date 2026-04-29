#!/bin/bash
# AlphaGenome local inference setup for TACC Stampede3 H100 nodes.
#
# Run this interactively to create the venv and pre-download model weights:
#   idev -p h100 -N 1 -n 1 -t 1:00:00
#   bash setup-stampede3.sh
#
# Stampede3 H100 nodes have 4x H100 SXM5 GPUs per node (vs LS6's 2x H100 PCIe).
# CUDA 12.8+ is required -- a TACC contact flagged that AlphaFold hit issues
# with newer CUDA, so verify the loaded module version explicitly.

set -euo pipefail

VENV_DIR="$SCRATCH/alphagenome-stampede3"

echo "=== AlphaGenome Stampede3 benchmark environment setup ==="

# Adjust these module names if `module avail` shows different versions.
module load python3
module load cuda

# Sanity-check CUDA version -- AlphaGenome / JAX need 12.8+ on Vista/Stampede3.
CUDA_VER="$(nvcc --version 2>/dev/null | grep -oE 'release [0-9]+\.[0-9]+' | awk '{print $2}' || echo unknown)"
echo "Loaded CUDA: ${CUDA_VER}"
case "$CUDA_VER" in
    12.[89]|12.1[0-9]|13.*|1[4-9].*)
        echo "CUDA version OK."
        ;;
    *)
        echo "WARN: CUDA ${CUDA_VER} may be too old. AlphaGenome/JAX wheels expect 12.8+." >&2
        echo "      Check 'module avail cuda' and load a newer version before continuing." >&2
        ;;
esac

if [ -d "$VENV_DIR" ]; then
    echo "Venv already exists at $VENV_DIR, activating..."
else
    echo "Creating venv at $VENV_DIR..."
    python3 -m venv "$VENV_DIR"
fi

source "$VENV_DIR/bin/activate"

echo "Installing dependencies..."
pip install --upgrade pip
pip install jax[cuda12] alphagenome-research

echo ""
echo "Pre-downloading model weights from HuggingFace..."
python3 -c "
from alphagenome_research.model import dna_model
model = dna_model.create_from_huggingface('all_folds')
print('Model weights downloaded and cached successfully.')
"

echo ""
echo "=== Setup complete ==="
echo "Venv: $VENV_DIR"
echo "Submit the benchmark with: sbatch run-stampede3.sh"
