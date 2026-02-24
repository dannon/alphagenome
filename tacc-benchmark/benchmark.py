#!/usr/bin/env python
"""
AlphaGenome local inference benchmark for TACC Lonestar6 H100.

Tests model loading and prediction at multiple sequence lengths,
reporting VRAM usage and timing at each step. Sequence lengths match
the options exposed in the Galaxy tool wrappers.
"""

import time
import jax
from alphagenome_research.model import dna_model
from alphagenome.data import genome


SEQ_LENGTHS = {
    "16KB": 16_384,
    "128KB": 131_072,
    "512KB": 524_288,
    "1MB": 1_048_576,
}

CHROM = "chr1"
POSITION = 1_000_000


def report_vram():
    for dev in jax.devices():
        stats = dev.memory_stats()
        if stats:
            current = stats.get("bytes_in_use", 0) / 1e9
            peak = stats.get("peak_bytes_in_use", 0) / 1e9
            total = stats.get("bytes_limit", 0) / 1e9
            print(f"  {dev}: {current:.1f}/{total:.1f} GB "
                  f"(peak {peak:.1f} GB)")


def main():
    print("=" * 60)
    print("AlphaGenome Local Inference Benchmark")
    print("=" * 60)

    devices = jax.devices()
    print(f"\nJAX backend: {jax.default_backend()}")
    print(f"Devices:     {devices}")
    report_vram()

    # --- Model loading ---
    print(f"\n--- Loading model (all_folds) ---")
    t0 = time.time()
    model = dna_model.create_from_huggingface("all_folds")
    print(f"Loaded in {time.time() - t0:.1f}s")
    report_vram()

    # --- Predictions at each sequence length ---
    assembly = genome.Assembly.HG38

    for label, seq_len in SEQ_LENGTHS.items():
        print(f"\n--- Predict: {label} ({seq_len:,} bp) ---")

        # First call includes JAX JIT compilation
        try:
            t0 = time.time()
            model.predict(
                assembly=assembly,
                chrom=CHROM,
                position=POSITION,
                sequence_length=seq_len,
            )
            jit_time = time.time() - t0
            print(f"  1st call (JIT compile): {jit_time:.1f}s")
            report_vram()
        except Exception as e:
            print(f"  FAILED on 1st call: {e}")
            report_vram()
            continue

        # Second call is steady-state — the number that matters
        try:
            t0 = time.time()
            model.predict(
                assembly=assembly,
                chrom=CHROM,
                position=POSITION + seq_len,
                sequence_length=seq_len,
            )
            steady_time = time.time() - t0
            print(f"  2nd call (compiled):    {steady_time:.1f}s")
            report_vram()
        except Exception as e:
            print(f"  FAILED on 2nd call: {e}")
            report_vram()

    # --- Summary ---
    print(f"\n{'=' * 60}")
    print("Final VRAM state:")
    report_vram()
    print("Done.")


if __name__ == "__main__":
    main()
