# AlphaGenome Galaxy Tools

Galaxy tool wrappers for Google DeepMind's [AlphaGenome](https://deepmind.google/discover/blog/alphagenome/) genomic foundation model.

Supports human (hg38) and mouse (mm10). No reference genome file needed — the API handles sequence context internally. All tools can swap between the cloud API and a local HuggingFace model for TACC deployment.

## Tools

### Variant Effect (`alphagenome_variant_effect`)

Scores genetic variants using `predict_variant()`. Computes max absolute log-fold-change between reference and alternate track predictions for selected output types. Annotates the input VCF with per-type effect scores.

**Input:** VCF → **Output:** Annotated VCF with `AG_*_LFC` INFO fields

### Variant Scorer (`alphagenome_variant_scorer`)

Scores variants using `score_variant()` with `RECOMMENDED_VARIANT_SCORERS` for server-side gene-level aggregation, spatial masking, and empirical quantile normalization. Richer output than Variant Effect — returns per-gene, per-track, per-scorer results via `tidy_scores()`.

**Input:** VCF → **Output:** Tabular (one row per variant × gene × track × scorer)

### ISM Scanner (`alphagenome_ism_scanner`)

In-silico saturation mutagenesis via `score_ism_variants()`. Systematically mutates every position in a region to all 3 alternative bases and scores each, replacing expensive wet-lab saturation mutagenesis. Server-side chunking with configurable parallelism.

**Input:** BED → **Output:** Tabular (one row per position × alt base × gene × track)

### Interval Predictor (`alphagenome_interval_predictor`)

Predicts regulatory tracks for genomic intervals using `predict_interval()`. No variants — just baseline characterization of chromatin, expression, and splicing landscapes. Summary mode (mean/max per track) or binned mode (spatial resolution within intervals).

**Input:** BED → **Output:** Tabular (summary or binned)

### Sequence Predictor (`alphagenome_sequence_predictor`)

Predicts regulatory tracks from raw DNA sequence using `predict_sequence()`. No genomic coordinates needed — designed for synthetic biology and non-reference assemblies. Short sequences are N-padded; long sequences are center-trimmed.

**Input:** FASTA → **Output:** Tabular (summary or binned)

## Quick Start

```bash
# Lint all tools
planemo lint tools/alphagenome/*/

# Serve all tools in a local Galaxy instance
planemo serve tools/alphagenome/*/

# Run any tool standalone (requires .venv with alphagenome package + API key)
.venv/bin/python tools/alphagenome/alphagenome_variant_effect/alphagenome_variant_effect.py \
    --input test_input.vcf --output out.vcf \
    --api-key $ALPHAGENOME_API_KEY \
    --output-types RNA_SEQ --max-variants 3 --verbose
```

## Dependencies

- `alphagenome` Python package (pip only, not in conda — must be pre-installed)
- `cyvcf2`, `numpy`, `pandas` (conda or pip)
- `planemo` for Galaxy tool development/testing

## Citation

Avsec et al. (2025). "Predicting the impact of genetic variants on chromatin, genes, and RNA processing with a unified model." *Nature*. DOI: [10.1038/s41586-025-10014-0](https://doi.org/10.1038/s41586-025-10014-0)
