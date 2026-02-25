# AlphaGenome Local Inference Benchmark (TACC Lonestar6)

Tests whether AlphaGenome's open-weight research model runs on LS6's H100 nodes, and measures VRAM usage and inference speed at each sequence length the Galaxy tools support.

## Background

The [Galaxy AlphaGenome wrappers](https://github.com/galaxyproject/tools-iuc/tree/master/tools/alphagenome) currently use the cloud API, but some use cases involve protected data that can't leave the compute environment. DeepMind [recommends at least an H100](https://github.com/google-deepmind/alphagenome_research) for local inference. LS6 has 4 nodes with 2x H100 PCIe 80GB each in the `gpu-h100` queue.

## Setup

Get an interactive session on an H100 node and run the setup script to create a Python venv and pre-download model weights (needs network access):

```bash
idev -p gpu-h100 -N 1 -n 1 -t 1:00:00
bash setup.sh
```

This installs JAX with CUDA support and `alphagenome-research` into `$SCRATCH/alphagenome-test`.

## Running the benchmark

Submit as a batch job:

```bash
sbatch run.sh
```

Output goes to `alphagenome-bench-<jobid>.out`. The benchmark:

1. Loads the model (`all_folds` ensemble from HuggingFace)
2. Runs predictions at 16KB, 128KB, 512KB, and 1MB sequence lengths
3. For each length, runs twice — first call includes JAX JIT compilation overhead, second is steady-state
4. Reports current and peak VRAM usage at every step

## What to look for in the output

- **Does it load?** If the model doesn't fit in 80GB VRAM you'll see an OOM immediately.
- **Which sequence lengths work?** 1MB is the default in the Galaxy tools and the important one. If it OOMs at 1MB but works at 512KB, that's useful to know.
- **Steady-state speed.** DeepMind reports ~300ms per 1MB prediction on H100. The second call at each length shows real throughput without JIT overhead.
- **Peak VRAM.** This directly answers whether an 80GB A100 could also work. (Note: LS6's A100s are only 40GB, so they're likely too small regardless.)

## Queue details

| | gpu-h100 | gpu-a100 |
|---|---|---|
| GPUs per node | 2x H100 80GB | 3x A100 40GB |
| Max nodes | 1 | 8 |
| Max walltime | 48h | 48h |
| SU cost | 6/node-hr | 4/node-hr |
| Max concurrent jobs | 1 | - |

The benchmark requests a single GPU (`--gres=gpu:1`) for 1 hour, which should be plenty.
