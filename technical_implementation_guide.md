# AlphaGenome Galaxy Tools - Technical Implementation Guide

**Version:** 1.0  
**Date:** June 25, 2025  
**Purpose:** Bridge between PRDs and implementation

---

## Table of Contents

1. [Development Environment Setup](#development-environment-setup)
2. [AlphaGenome API Integration Patterns](#alphagenome-api-integration-patterns)
3. [Galaxy Tool Development Best Practices](#galaxy-tool-development-best-practices)
4. [Code Organization Structure](#code-organization-structure)
5. [Test Data Specifications](#test-data-specifications)
6. [Common Pitfalls and Solutions](#common-pitfalls-and-solutions)
7. [Performance Optimization Guidelines](#performance-optimization-guidelines)
8. [Security Considerations](#security-considerations)
9. [Deployment Checklist](#deployment-checklist)

---

## Development Environment Setup

### Prerequisites

```bash
# Python environment
python >= 3.8
pip install alphagenome
pip install pysam
pip install cyvcf2
pip install requests
pip install numpy pandas

# Galaxy development
planemo >= 0.74.0
galaxy-tool-util
```

### Local Galaxy Instance

```bash
# Quick Galaxy setup for testing
planemo serve --galaxy_branch release_24.0

# Or full development instance
git clone https://github.com/galaxyproject/galaxy.git
cd galaxy
./run.sh
```

### Directory Structure

```
alphagenome-galaxy-tools/
├── tools/
│   ├── alphagenome_variant_scorer/
│   │   ├── alphagenome_variant_scorer.xml
│   │   ├── alphagenome_variant_scorer.py
│   │   ├── test-data/
│   │   └── macros.xml
│   ├── alphagenome_expression/
│   ├── alphagenome_splicing/
│   └── alphagenome_promoter_design/
├── shared/
│   ├── alphagenome_client.py
│   ├── sequence_utils.py
│   └── cache_manager.py
├── workflows/
├── docs/
└── test/
```

---

## AlphaGenome API Integration Patterns

### Basic API Client Wrapper

```python
# shared/alphagenome_client.py
import time
import logging
from typing import Dict, List, Optional
import alphagenome

class AlphaGenomeClient:
    """Wrapper for AlphaGenome API with rate limiting and caching."""
    
    def __init__(self, api_key: str, cache_dir: Optional[str] = None):
        self.api_key = api_key
        self.cache_dir = cache_dir
        self.rate_limit_delay = 0.1  # 100ms between requests
        self.last_request_time = 0
        self.session = self._create_session()
        
    def _create_session(self):
        """Initialize AlphaGenome session with API key."""
        # Initialize according to AlphaGenome docs
        return alphagenome.Client(api_key=self.api_key)
        
    def _rate_limit(self):
        """Implement rate limiting between API calls."""
        current_time = time.time()
        time_since_last = current_time - self.last_request_time
        if time_since_last < self.rate_limit_delay:
            time.sleep(self.rate_limit_delay - time_since_last)
        self.last_request_time = time.time()
        
    def predict_variant_effects(self, 
                              chrom: str, 
                              pos: int, 
                              ref: str, 
                              alt: str,
                              sequence_context: str,
                              predictions: List[str]) -> Dict:
        """Predict effects of a single variant."""
        self._rate_limit()
        
        try:
            # Check cache first
            cache_key = f"{chrom}:{pos}:{ref}>{alt}"
            if cached := self._get_from_cache(cache_key):
                return cached
                
            # Make API call
            result = self.session.predict_variant(
                sequence=sequence_context,
                variant_pos=pos,
                ref_allele=ref,
                alt_allele=alt,
                outputs=predictions
            )
            
            # Cache result
            self._save_to_cache(cache_key, result)
            
            return result
            
        except Exception as e:
            logging.error(f"API error for variant {chrom}:{pos}: {e}")
            raise
```

### Batch Processing Pattern

```python
def process_variants_batch(variants: List[Dict], 
                          client: AlphaGenomeClient,
                          batch_size: int = 50) -> List[Dict]:
    """Process variants in batches with progress reporting."""
    results = []
    total = len(variants)
    
    for i in range(0, total, batch_size):
        batch = variants[i:i+batch_size]
        batch_results = []
        
        # Process batch with retry logic
        for attempt in range(3):
            try:
                for variant in batch:
                    result = client.predict_variant_effects(**variant)
                    batch_results.append(result)
                break
            except RateLimitError:
                wait_time = 2 ** attempt
                logging.info(f"Rate limited, waiting {wait_time}s")
                time.sleep(wait_time)
        
        results.extend(batch_results)
        
        # Progress reporting for Galaxy
        progress = (i + len(batch)) / total * 100
        print(f"Progress: {progress:.1f}%", flush=True)
        
    return results
```

### Caching Strategy

```python
# shared/cache_manager.py
import json
import hashlib
from pathlib import Path

class CacheManager:
    """Manage API result caching to minimize redundant calls."""
    
    def __init__(self, cache_dir: str):
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(exist_ok=True)
        
    def get_cache_key(self, **params) -> str:
        """Generate cache key from parameters."""
        key_str = json.dumps(params, sort_keys=True)
        return hashlib.md5(key_str.encode()).hexdigest()
        
    def get(self, key: str) -> Optional[Dict]:
        """Retrieve from cache if exists."""
        cache_file = self.cache_dir / f"{key}.json"
        if cache_file.exists():
            with open(cache_file) as f:
                return json.load(f)
        return None
        
    def set(self, key: str, value: Dict):
        """Save to cache."""
        cache_file = self.cache_dir / f"{key}.json"
        with open(cache_file, 'w') as f:
            json.dump(value, f)
```

---

## Galaxy Tool Development Best Practices

### Tool XML Structure

```xml
<tool id="alphagenome_variant_scorer" name="AlphaGenome Variant Scorer" version="@TOOL_VERSION@">
    <description>Predict functional effects of genetic variants</description>
    
    <macros>
        <import>macros.xml</import>
    </macros>
    
    <requirements>
        <requirement type="package" version="@ALPHAGENOME_VERSION@">alphagenome</requirement>
        <requirement type="package" version="0.6.5">pysam</requirement>
    </requirements>
    
    <version_command>python '$__tool_directory__/alphagenome_variant_scorer.py' --version</version_command>
    
    <command detect_errors="exit_code"><![CDATA[
        @PREPARE_ENVIRONMENT@
        
        python '$__tool_directory__/alphagenome_variant_scorer.py'
            --input '$input_vcf'
            --output '$output_vcf'
            --api-key '$api_key'
            --cache-dir '$__job_directory__/cache'
            @COMMON_OPTIONS@
            #if $advanced.custom_window
                --window-size $advanced.window_size
            #end if
    ]]></command>
```

### Shared Macros

```xml
<!-- macros.xml -->
<macros>
    <token name="@TOOL_VERSION@">1.0.0</token>
    <token name="@ALPHAGENOME_VERSION@">0.1.0</token>
    
    <xml name="citations">
        <citations>
            <citation type="doi">10.1038/alphagenome2025</citation>
        </citations>
    </xml>
    
    <token name="@PREPARE_ENVIRONMENT@">
        export ALPHAGENOME_CACHE_DIR="\$_GALAXY_JOB_TMP_DIR/alphagenome_cache" &&
        mkdir -p "\$ALPHAGENOME_CACHE_DIR" &&
    </token>
    
    <token name="@COMMON_OPTIONS@">
        --predictions '$predictions'
        --max-variants $max_variants
        --threads \${GALAXY_SLOTS:-1}
    </token>
</macros>
```

### Error Handling

```python
# Standard error handling pattern for Galaxy tools
import sys
import logging

def setup_logging(verbose=False):
    """Configure logging for Galaxy tool."""
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(sys.stderr)
        ]
    )

def main():
    try:
        # Tool logic here
        pass
    except AlphaGenomeAPIError as e:
        logging.error(f"AlphaGenome API error: {e}")
        sys.exit(1)
    except Exception as e:
        logging.error(f"Unexpected error: {e}", exc_info=True)
        sys.exit(2)
```

---

## Code Organization Structure

### Shared Utilities

```python
# shared/sequence_utils.py
from typing import Tuple
import pysam

def extract_sequence_context(fasta_file: str, 
                           chrom: str, 
                           pos: int, 
                           window: int = 1000) -> str:
    """Extract sequence context around a position."""
    with pysam.FastaFile(fasta_file) as fasta:
        start = max(0, pos - window // 2)
        end = pos + window // 2
        try:
            return fasta.fetch(chrom, start, end)
        except:
            # Handle edge cases
            seq_len = fasta.get_reference_length(chrom)
            start = max(0, start)
            end = min(seq_len, end)
            return fasta.fetch(chrom, start, end)

def validate_sequence(seq: str) -> Tuple[bool, str]:
    """Validate DNA sequence."""
    valid_chars = set('ACGTNacgtn')
    invalid = set(seq) - valid_chars
    if invalid:
        return False, f"Invalid characters: {invalid}"
    return True, ""
```

### Tool-Specific Modules

```python
# tools/alphagenome_variant_scorer/variant_processor.py
class VariantProcessor:
    """Process variants for AlphaGenome scoring."""
    
    def __init__(self, vcf_file: str, reference: str):
        self.vcf = cyvcf2.VCF(vcf_file)
        self.reference = pysam.FastaFile(reference)
        
    def process(self):
        """Main processing logic."""
        # Implementation here
        pass
```

---

## Test Data Specifications

### Minimal Test VCF

```
##fileformat=VCFv4.2
##reference=GRCh38
##INFO=<ID=AG_EXPR,Number=1,Type=Float,Description="AlphaGenome expression impact">
##INFO=<ID=AG_SPLICE,Number=1,Type=Float,Description="AlphaGenome splicing impact">
#CHROM	POS	ID	REF	ALT	QUAL	FILTER	INFO
chr1	12345	.	A	G	.	PASS	.
chr1	67890	.	CTG	C	.	PASS	.
chr2	11111	.	G	A,T	.	PASS	.
```

### Test Reference FASTA

```
>chr1
NNNNNNNNNNACTGACTGACTGANNNNNNNNNN
>chr2  
NNNNNNNNNNGTCAGTCAGTCAGNNNNNNNNNN
```

### Expected Output Format

```
##fileformat=VCFv4.2
##AlphaGenomeVersion=0.1.0
##AlphaGenomeCommand=variant_scorer.py --predictions expression,splicing
#CHROM	POS	ID	REF	ALT	QUAL	FILTER	INFO
chr1	12345	.	A	G	.	PASS	AG_EXPR=0.823;AG_SPLICE=0.102
```

---

## Common Pitfalls and Solutions

### 1. API Rate Limiting

**Problem:** 429 errors when processing many variants  
**Solution:** 
- Implement exponential backoff
- Use batch processing with delays
- Cache all results aggressively

### 2. Memory Issues with Large VCFs

**Problem:** OOM errors on large files  
**Solution:**
```python
# Stream processing instead of loading all
for variant in cyvcf2.VCF(vcf_file):
    process_single_variant(variant)
    # Don't accumulate in memory
```

### 3. Coordinate System Mismatches

**Problem:** Off-by-one errors between VCF (1-based) and API (0-based)  
**Solution:**
```python
def vcf_to_api_coords(vcf_pos):
    """Convert VCF 1-based to API 0-based."""
    return vcf_pos - 1
```

### 4. Galaxy-Specific Issues

**Problem:** Tool fails in Galaxy but works locally  
**Solution:**
- Use `$__job_directory__` for temp files
- Respect `$GALAXY_SLOTS` for threading
- Write to stderr for logging
- Use exit codes correctly

---

## Performance Optimization Guidelines

### 1. Implement Smart Caching

```python
# Cache at multiple levels
# 1. API results
# 2. Sequence contexts
# 3. Parsed VCF records

cache_levels = {
    'api_results': 7 * 24 * 3600,  # 7 days
    'sequences': 30 * 24 * 3600,    # 30 days
    'vcf_parse': 1 * 3600           # 1 hour
}
```

### 2. Batch Size Optimization

```python
def get_optimal_batch_size(total_variants):
    """Dynamic batch sizing based on job size."""
    if total_variants < 100:
        return 10
    elif total_variants < 1000:
        return 50
    else:
        return 100
```

### 3. Parallel Processing

```python
from concurrent.futures import ThreadPoolExecutor

def parallel_predict(variants, client, max_workers=4):
    """Process variants in parallel threads."""
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = []
        for variant in variants:
            future = executor.submit(client.predict_variant_effects, **variant)
            futures.append((variant, future))
        
        results = []
        for variant, future in futures:
            try:
                result = future.result(timeout=30)
                results.append((variant, result))
            except Exception as e:
                logging.error(f"Failed for variant: {e}")
                
    return results
```

---

## Security Considerations

### API Key Management

```python
def get_api_key(args, galaxy_env):
    """Secure API key retrieval."""
    # Priority order:
    # 1. User-provided (masked input)
    # 2. Admin-configured
    # 3. Environment variable
    
    if args.api_key and args.api_key != 'admin_configured':
        return args.api_key
    elif os.environ.get('ALPHAGENOME_API_KEY'):
        return os.environ['ALPHAGENOME_API_KEY']
    else:
        raise ValueError("No API key provided")
```

### Input Validation

```python
def validate_inputs(vcf_file, reference_file):
    """Validate all inputs before processing."""
    # Check file existence
    if not os.path.exists(vcf_file):
        raise FileNotFoundError(f"VCF file not found: {vcf_file}")
        
    # Check file format
    try:
        vcf = cyvcf2.VCF(vcf_file)
        vcf.close()
    except:
        raise ValueError("Invalid VCF file format")
        
    # Check reference
    try:
        ref = pysam.FastaFile(reference_file)
        ref.close()
    except:
        raise ValueError("Invalid reference FASTA")
```

---

## Deployment Checklist

### Pre-deployment Testing

- [ ] Unit tests pass
- [ ] Integration tests with Galaxy
- [ ] Performance benchmarks meet requirements
- [ ] API rate limiting tested
- [ ] Error handling for all edge cases
- [ ] Documentation complete

### Tool Package Structure

```
alphagenome_variant_scorer/
├── alphagenome_variant_scorer.xml
├── alphagenome_variant_scorer.py
├── macros.xml
├── test-data/
│   ├── input.vcf
│   ├── reference.fa
│   └── expected_output.vcf
├── tool_data_table_conf.xml.sample
└── README.md
```

### Galaxy Tool Shed Preparation

```yaml
# .shed.yml
name: alphagenome_variant_scorer
owner: galaxy-alphagenome
description: Predict variant effects using AlphaGenome
long_description: |
  This tool uses Google DeepMind's AlphaGenome model to predict
  the functional effects of genetic variants.
categories:
  - Variant Analysis
  - Machine Learning
homepage_url: https://github.com/galaxy-alphagenome/tools
remote_repository_url: https://github.com/galaxy-alphagenome/tools
```

### Continuous Integration

```yaml
# .github/workflows/ci.yml
name: CI
on: [push, pull_request]
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      - name: Lint tools
        run: planemo lint tools/
      - name: Run tests
        run: planemo test --galaxy_branch release_24.0 tools/
```

---

## Quick Start Commands

```bash
# Initialize new tool
planemo tool_init --id alphagenome_expression \
    --name "AlphaGenome Expression Predictor"

# Test tool locally
planemo test tools/alphagenome_variant_scorer/

# Serve with Galaxy
planemo serve tools/alphagenome_variant_scorer/

# Create tool package
planemo shed_create --shed_target toolshed

# Update tool
planemo shed_update --shed_target toolshed
```

---

## Support Resources

- AlphaGenome API Docs: https://www.alphagenomedocs.com/
- Galaxy Tool Development: https://training.galaxyproject.org/
- Community Support: https://help.galaxyproject.org/

---

## Next Steps

1. Set up development environment
2. Implement shared API client
3. Build first tool (Variant Scorer)
4. Test thoroughly
5. Deploy to test server
6. Gather user feedback
7. Iterate and improve