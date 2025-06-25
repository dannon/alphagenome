# AlphaGenome Variant Scorer

A Galaxy tool for predicting functional effects of genetic variants using Google DeepMind's AlphaGenome model.

## Overview

This tool processes VCF files containing genetic variants and annotates them with AlphaGenome predictions for various molecular effects including gene expression impact, splicing disruption, chromatin accessibility changes, and conservation scores.

## Features

- **Multiple prediction types**: Expression, splicing, chromatin, conservation
- **Robust API integration**: Rate limiting, caching, error handling
- **Scalable processing**: Batch processing with progress reporting
- **Galaxy integration**: Full Galaxy tool wrapper with proper data types
- **Comprehensive testing**: Unit tests and Galaxy integration tests

## Requirements

- Python 3.9+
- pysam >= 0.22.0
- cyvcf2 >= 0.30.24
- requests >= 2.31.0
- AlphaGenome API key

## Installation

1. Copy the tool directory to your Galaxy `tools/` directory
2. Copy the shared utilities to the appropriate location
3. Add the tool to your Galaxy tool configuration
4. Install the required conda packages

## Usage

### Input Files

- **VCF file**: Standard VCF format (v4.1+) containing genetic variants
- **Reference genome**: FASTA format reference genome (built-in or from history)
- **API key**: AlphaGenome API key for accessing predictions

### Parameters

- **Prediction types**: Select which predictions to include
- **Max variants**: Limit processing due to API quotas (default: 1000)
- **Window size**: Genomic context size around variants (default: 1000 bp)
- **Batch size**: API request batch size (default: 50)

### Output

Annotated VCF file with additional INFO fields:
- `AG_EXPR`: Expression impact score (0-1)
- `AG_SPLICE`: Splicing disruption score (0-1)
- `AG_CHROM`: Chromatin impact score (0-1)
- `AG_CONS`: Conservation score (0-1)

## API Integration

The tool integrates with the AlphaGenome API using:

- **Rate limiting**: Automatic throttling to respect API quotas
- **Caching**: Persistent caching to avoid redundant API calls
- **Error handling**: Comprehensive error handling with retries
- **Batch processing**: Efficient batching for large variant sets

## Testing

### Unit Tests

Run unit tests for individual components:

```bash
python -m pytest shared/
```

### Galaxy Tests

Test with planemo:

```bash
planemo test tools/alphagenome/alphagenome_variant_scorer/
```

### Integration Tests

Test with sample data:

```bash
planemo serve tools/alphagenome/alphagenome_variant_scorer/
```

## Performance

- **Processing time**: ~5 minutes for 1000 variants (excluding API latency)
- **Memory usage**: <2GB for typical jobs
- **API efficiency**: Intelligent caching reduces redundant calls
- **Scalability**: Batch processing handles large variant sets

## Limitations

- **Non-commercial use only**: Per AlphaGenome terms of service
- **API quotas**: Large-scale processing may require multiple runs
- **Human genome focus**: Optimized for human genetic variants
- **Network dependency**: Requires internet access to AlphaGenome API

## File Structure

```
alphagenome_variant_scorer/
├── alphagenome_variant_scorer.xml     # Galaxy tool wrapper
├── alphagenome_variant_scorer.py      # Main Python script
├── macros.xml                         # Shared XML macros
├── test-data/                         # Test data files
│   ├── test_variants.vcf              # Sample VCF input
│   ├── test_reference.fa              # Sample reference
│   └── expected_output_*.vcf          # Expected outputs
└── README.md                          # This file
```

## Contributing

1. Follow Galaxy tool development best practices
2. Include comprehensive tests for new functionality
3. Update documentation for any changes
4. Ensure compatibility with Galaxy tool testing framework

## Support

- **AlphaGenome Documentation**: https://www.alphagenomedocs.com/
- **Galaxy Help**: https://help.galaxyproject.org/
- **Tool Issues**: Report at the appropriate repository

## Citation

If you use this tool in your research, please cite:

*Avsec et al. (2025). "AlphaGenome: A unified model for deciphering the regulatory code of DNA sequences"*

## License

For non-commercial research use only, in accordance with AlphaGenome terms of service.