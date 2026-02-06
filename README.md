# AlphaGenome Galaxy Tools

Galaxy tool wrappers for Google DeepMind's [AlphaGenome](https://deepmind.google/discover/blog/alphagenome/) genomic foundation model.

## Current Status

**POC variant effect tool** (`tools/alphagenome/alphagenome_variant_effect/`) — scores genetic variants from a VCF using the real `alphagenome` Python package (`predict_variant()` API). Computes max absolute log-fold-change between reference and alternate track predictions for selected output types (RNA-seq, ATAC, splice sites, etc.).

Supports human (hg38) and mouse (mm10). No reference genome file needed — the API handles sequence context internally.

Designed so the model creation can swap between API and local HuggingFace model for future TACC deployment.

## Quick Start

```bash
# Lint the tool XML
planemo lint tools/alphagenome/alphagenome_variant_effect/

# Serve in a local Galaxy instance
planemo serve tools/alphagenome/alphagenome_variant_effect/

# Run standalone (requires alphagenome package + API key)
python3 tools/alphagenome/alphagenome_variant_effect/alphagenome_variant_effect.py \
    --input test_input.vcf --output out.vcf \
    --api-key $ALPHAGENOME_API_KEY \
    --output-types RNA_SEQ --max-variants 3 --verbose
```

## Dependencies

- `alphagenome` Python package (pip, not in conda — must be pre-installed)
- `cyvcf2`, `numpy` (conda or pip)
- `planemo` for Galaxy tool development/testing

## Next Steps

- Set up a project venv with dependencies and test end-to-end with a real API key
- Build a small ClinVar chr22 test set for quality validation
- Add `score_variant()` support with `RECOMMENDED_VARIANT_SCORERS`
- Batch prediction via `predict_variants()`
- Local model Galaxy XML variant for TACC deployment

## Citation

Avsec et al. (2025). "Predicting the impact of genetic variants on chromatin, genes, and RNA processing with a unified model." *Nature*. DOI: [10.1038/s41586-025-10014-0](https://doi.org/10.1038/s41586-025-10014-0)
