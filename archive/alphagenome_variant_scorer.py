#!/usr/bin/env python
"""
AlphaGenome Variant Scorer for Galaxy

Predicts functional effects of genetic variants using AlphaGenome API.
"""

import argparse
import json
import logging
import os
import sys
import time
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import pysam
from cyvcf2 import VCF, Writer

# Import shared modules (would be in parent directory in real implementation)
# from shared.alphagenome_client import AlphaGenomeClient
# from shared.cache_manager import CacheManager
# from shared.sequence_utils import extract_sequence_context

__version__ = "1.0.0"


class AlphaGenomeClient:
    """Wrapper for AlphaGenome API with rate limiting and caching."""
    
    def __init__(self, api_key: str, cache_manager: Optional['CacheManager'] = None):
        self.api_key = api_key
        self.cache_manager = cache_manager
        self.rate_limit_delay = 0.1  # 100ms between requests
        self.last_request_time = 0
        
        # Initialize AlphaGenome session
        # self.session = alphagenome.Client(api_key=self.api_key)
        
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
        
        # Check cache first
        cache_key = f"{chrom}:{pos}:{ref}>{alt}:{','.join(predictions)}"
        if self.cache_manager:
            cached = self.cache_manager.get(cache_key)
            if cached:
                logging.debug(f"Cache hit for {cache_key}")
                return cached
        
        try:
            # TODO: Real API call would go here
            # result = self.session.predict_variant(
            #     sequence=sequence_context,
            #     variant_pos=pos,
            #     ref_allele=ref,
            #     alt_allele=alt,
            #     outputs=predictions
            # )
            
            # Mock result for template
            result = {
                'expression': 0.823,
                'splicing': 0.102,
                'chromatin': 0.456,
                'conservation': 0.901
            }
            
            # Filter to requested predictions
            result = {k: v for k, v in result.items() if k in predictions}
            
            # Cache result
            if self.cache_manager:
                self.cache_manager.set(cache_key, result)
            
            return result
            
        except Exception as e:
            logging.error(f"API error for variant {chrom}:{pos}: {e}")
            raise


class CacheManager:
    """Simple cache manager for API results."""
    
    def __init__(self, cache_dir: str):
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        
    def _get_cache_file(self, key: str) -> Path:
        """Get cache file path for key."""
        # Use first 2 chars for subdirectory to avoid too many files in one dir
        safe_key = key.replace(':', '_').replace('>', '_')
        subdir = self.cache_dir / safe_key[:2]
        subdir.mkdir(exist_ok=True)
        return subdir / f"{safe_key}.json"
        
    def get(self, key: str) -> Optional[Dict]:
        """Retrieve from cache if exists."""
        cache_file = self._get_cache_file(key)
        if cache_file.exists():
            try:
                with open(cache_file) as f:
                    return json.load(f)
            except:
                # Invalid cache file, remove it
                cache_file.unlink()
        return None
        
    def set(self, key: str, value: Dict):
        """Save to cache."""
        cache_file = self._get_cache_file(key)
        with open(cache_file, 'w') as f:
            json.dump(value, f)


class VariantScorer:
    """Main class for scoring variants with AlphaGenome."""
    
    def __init__(self, 
                 vcf_path: str,
                 reference_path: str,
                 output_path: str,
                 api_key: str,
                 predictions: List[str],
                 window_size: int = 1000,
                 max_variants: int = 1000,
                 cache_dir: Optional[str] = None):
        
        self.vcf_path = vcf_path
        self.reference_path = reference_path
        self.output_path = output_path
        self.predictions = predictions
        self.window_size = window_size
        self.max_variants = max_variants
        
        # Initialize components
        self.cache_manager = CacheManager(cache_dir) if cache_dir else None
        self.client = AlphaGenomeClient(api_key, self.cache_manager)
        self.reference = pysam.FastaFile(reference_path)
        
        # Stats tracking
        self.stats = {
            'total_variants': 0,
            'processed_variants': 0,
            'skipped_variants': 0,
            'api_calls': 0,
            'cache_hits': 0,
            'errors': 0
        }
        
    def extract_sequence_context(self, chrom: str, pos: int) -> str:
        """Extract sequence context around variant position."""
        # Convert to 0-based for pysam
        pos_0based = pos - 1
        
        # Calculate window boundaries
        start = max(0, pos_0based - self.window_size // 2)
        end = pos_0based + self.window_size // 2
        
        try:
            # Get chromosome length
            chrom_length = self.reference.get_reference_length(chrom)
            
            # Adjust boundaries if needed
            if end > chrom_length:
                end = chrom_length
                start = max(0, end - self.window_size)
                
            return self.reference.fetch(chrom, start, end)
            
        except Exception as e:
            logging.warning(f"Failed to extract sequence for {chrom}:{pos}: {e}")
            raise
            
    def process_variant(self, variant) -> Optional[Dict]:
        """Process a single variant and return predictions."""
        chrom = variant.CHROM
        pos = variant.POS
        ref = variant.REF
        
        # Handle multiple alternate alleles
        results = {}
        
        for i, alt in enumerate(variant.ALT):
            if alt == ref:  # Skip if alt same as ref
                continue
                
            try:
                # Extract sequence context
                sequence = self.extract_sequence_context(chrom, pos)
                
                # Get predictions
                predictions = self.client.predict_variant_effects(
                    chrom=chrom,
                    pos=pos,
                    ref=ref,
                    alt=alt,
                    sequence_context=sequence,
                    predictions=self.predictions
                )
                
                results[alt] = predictions
                self.stats['api_calls'] += 1
                
            except Exception as e:
                logging.error(f"Failed to process {chrom}:{pos} {ref}>{alt}: {e}")
                self.stats['errors'] += 1
                continue
                
        return results if results else None
        
    def add_info_headers(self, vcf_reader):
        """Add AlphaGenome INFO field headers to VCF."""
        info_fields = {
            'expression': ('AG_EXPR', 'A', 'Float', 'AlphaGenome expression impact score'),
            'splicing': ('AG_SPLICE', 'A', 'Float', 'AlphaGenome splicing impact score'),
            'chromatin': ('AG_CHROM', 'A', 'Float', 'AlphaGenome chromatin impact score'),
            'conservation': ('AG_CONS', 'A', 'Float', 'AlphaGenome conservation score')
        }
        
        for pred in self.predictions:
            if pred in info_fields:
                field_id, number, dtype, desc = info_fields[pred]
                vcf_reader.add_info_to_header({
                    'ID': field_id,
                    'Number': number,
                    'Type': dtype,
                    'Description': desc
                })
                
        # Add processing info
        vcf_reader.add_to_header(f"##AlphaGenomeVersion={__version__}")
        vcf_reader.add_to_header(f"##AlphaGenomeCommand=Predictions: {','.join(self.predictions)}")
        
    def run(self):
        """Run the variant scoring pipeline."""
        logging.info(f"Starting AlphaGenome variant scoring")
        logging.info(f"Input VCF: {self.vcf_path}")
        logging.info(f"Reference: {self.reference_path}")
        logging.info(f"Predictions: {', '.join(self.predictions)}")
        
        # Open VCF for reading
        vcf_reader = VCF(self.vcf_path)
        
        # Add headers
        self.add_info_headers(vcf_reader)
        
        # Open output VCF for writing
        vcf_writer = Writer(self.output_path, vcf_reader)
        
        # Process variants
        for variant_num, variant in enumerate(vcf_reader):
            self.stats['total_variants'] += 1
            
            # Check variant limit
            if variant_num >= self.max_variants:
                logging.warning(f"Reached maximum variant limit ({self.max_variants})")
                self.stats['skipped_variants'] += 1
                continue
                
            # Progress reporting
            if variant_num % 100 == 0 and variant_num > 0:
                self._report_progress(variant_num)
                
            # Process variant
            results = self.process_variant(variant)
            
            if results:
                # Add predictions to INFO fields
                for alt, predictions in results.items():
                    alt_idx = variant.ALT.index(alt)
                    
                    for pred_type, score in predictions.items():
                        info_key = {
                            'expression': 'AG_EXPR',
                            'splicing': 'AG_SPLICE',
                            'chromatin': 'AG_CHROM',
                            'conservation': 'AG_CONS'
                        }.get(pred_type)
                        
                        if info_key:
                            # Set value for specific allele
                            if variant.INFO.get(info_key) is None:
                                variant.INFO[info_key] = [None] * len(variant.ALT)
                            variant.INFO[info_key][alt_idx] = round(score, 4)
                            
                self.stats['processed_variants'] += 1
            else:
                self.stats['skipped_variants'] += 1
                
            # Write variant
            vcf_writer.write_record(variant)
            
        # Close files
        vcf_writer.close()
        vcf_reader.close()
        
        # Final report
        self._report_final_stats()
        
    def _report_progress(self, variant_num: int):
        """Report progress to Galaxy."""
        progress = (variant_num / self.max_variants) * 100
        print(f"Progress: {progress:.1f}% ({variant_num} variants processed)", 
              flush=True)
              
    def _report_final_stats(self):
        """Report final statistics."""
        logging.info("=" * 50)
        logging.info("FINAL STATISTICS")
        logging.info("=" * 50)
        logging.info(f"Total variants: {self.stats['total_variants']}")
        logging.info(f"Processed variants: {self.stats['processed_variants']}")
        logging.info(f"Skipped variants: {self.stats['skipped_variants']}")
        logging.info(f"API calls made: {self.stats['api_calls']}")
        logging.info(f"Errors encountered: {self.stats['errors']}")
        
        if self.cache_manager:
            cache_hits = self.stats['api_calls'] - self.stats['processed_variants']
            logging.info(f"Cache hit rate: {cache_hits / max(1, self.stats['api_calls']) * 100:.1f}%")


def setup_logging(verbose: bool = False):
    """Configure logging for Galaxy tool."""
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(sys.stderr)
        ]
    )


def parse_arguments():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Score genetic variants using AlphaGenome predictions"
    )
    
    # Required arguments
    parser.add_argument('--input', '-i', required=True,
                       help='Input VCF file')
    parser.add_argument('--output', '-o', required=True,
                       help='Output VCF file')
    parser.add_argument('--reference', '-r', required=True,
                       help='Reference genome (FASTA)')
    parser.add_argument('--api-key', required=True,
                       help='AlphaGenome API key')
    
    # Prediction options
    parser.add_argument('--predictions', '-p', nargs='+',
                       choices=['expression', 'splicing', 'chromatin', 'conservation'],
                       default=['expression', 'splicing'],
                       help='Types of predictions to include')
    
    # Processing options
    parser.add_argument('--max-variants', type=int, default=1000,
                       help='Maximum number of variants to process')
    parser.add_argument('--window-size', type=int, default=1000,
                       help='Sequence context window size')
    parser.add_argument('--cache-dir', 
                       help='Directory for caching API results')
    
    # Other options
    parser.add_argument('--verbose', '-v', action='store_true',
                       help='Enable verbose logging')
    parser.add_argument('--version', action='version',
                       version=f'%(prog)s {__version__}')
    
    return parser.parse_args()


def main():
    """Main entry point."""
    args = parse_arguments()
    
    # Setup logging
    setup_logging(args.verbose)
    
    try:
        # Validate inputs
        if not os.path.exists(args.input):
            raise FileNotFoundError(f"Input VCF not found: {args.input}")
        if not os.path.exists(args.reference):
            raise FileNotFoundError(f"Reference genome not found: {args.reference}")
            
        # Create scorer and run
        scorer = VariantScorer(
            vcf_path=args.input,
            reference_path=args.reference,
            output_path=args.output,
            api_key=args.api_key,
            predictions=args.predictions,
            window_size=args.window_size,
            max_variants=args.max_variants,
            cache_dir=args.cache_dir
        )
        
        scorer.run()
        
        logging.info(f"Successfully wrote output to: {args.output}")
        
    except Exception as e:
        logging.error(f"Fatal error: {e}", exc_info=True)
        sys.exit(1)


if __name__ == '__main__':
    main()
