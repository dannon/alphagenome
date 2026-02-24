#!/bin/bash
# AlphaGenome local inference setup for TACC Lonestar6 H100 nodes.
#
# Run this interactively to create the venv and pre-download model weights:
#   idev -p gpu-h100 -N 1 -n 1 -t 1:00:00
#   bash setup.sh

set -euo pipefail

VENV_DIR="$SCRATCH/alphagenome-test"

echo "=== AlphaGenome benchmark environment setup ==="

module load python3/3.9.7

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
echo "Submit the benchmark with: sbatch run.sh"
