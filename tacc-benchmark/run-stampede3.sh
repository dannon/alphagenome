#!/bin/bash
#SBATCH -J alphagenome-bench
#SBATCH -p h100
#SBATCH -N 1
#SBATCH -n 1
#SBATCH -t 01:00:00
#SBATCH --gres=gpu:1
#SBATCH -o alphagenome-bench-%j.out
#SBATCH -e alphagenome-bench-%j.err

module load python3
module load cuda
source "$SCRATCH/alphagenome-stampede3/bin/activate"

nvidia-smi
python3 "$(dirname "$0")/benchmark.py"
