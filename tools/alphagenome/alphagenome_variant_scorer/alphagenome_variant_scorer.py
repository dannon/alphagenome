#!/usr/bin/env python
"""
AlphaGenome Variant Scorer for Galaxy

Predicts functional effects of genetic variants using AlphaGenome API.
"""

import argparse
import logging
import os
import sys
from pathlib import Path
from typing import Dict, List, Optional

import cyvcf2
from cyvcf2 import VCF, Writer

# Add shared directory to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent / "shared"))

from alphagenome_client import AlphaGenomeClient, AlphaGenomeAPIError, RateLimitError
from cache_manager import CacheManager
from sequence_utils import SequenceExtractor, SequenceError

__version__ = "1.0.0"


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
                 cache_dir: Optional[str] = None,
                 batch_size: int = 50):
        
        self.vcf_path = vcf_path
        self.reference_path = reference_path
        self.output_path = output_path
        self.predictions = predictions
        self.window_size = window_size
        self.max_variants = max_variants
        self.batch_size = batch_size
        
        # Initialize components
        self.cache_manager = CacheManager(cache_dir) if cache_dir else None
        self.client = AlphaGenomeClient(
            api_key=api_key, 
            cache_dir=cache_dir,
            rate_limit_delay=0.1  # 100ms between requests
        )
        
        # Initialize sequence extractor
        try:
            self.sequence_extractor = SequenceExtractor(reference_path)
        except SequenceError as e:
            logging.error(f"Failed to initialize sequence extractor: {e}")
            raise
        
        # Stats tracking
        self.stats = {
            'total_variants': 0,
            'processed_variants': 0,
            'skipped_variants': 0,
            'multiallelic_variants': 0,
            'api_errors': 0,
            'sequence_errors': 0
        }
        
    def process_variant(self, variant) -> Optional[Dict]:
        """Process a single variant and return predictions."""
        chrom = variant.CHROM
        pos = variant.POS
        ref = variant.REF
        
        # Handle multiple alternate alleles
        results = {}
        
        if len(variant.ALT) > 1:
            self.stats['multiallelic_variants'] += 1
            
        for i, alt in enumerate(variant.ALT):
            if alt == ref:  # Skip if alt same as ref
                continue
                
            try:
                # Extract sequence context
                context_info = self.sequence_extractor.extract_variant_context(
                    chrom=chrom,
                    pos=pos,
                    ref=ref,
                    alt=alt,
                    window_size=self.window_size
                )
                
                # Check if reference matches
                if not context_info['ref_matches']:
                    logging.warning(
                        f"Reference mismatch at {chrom}:{pos}: "
                        f"VCF has {ref}, reference has {context_info['actual_ref']}"
                    )
                
                # Get predictions from AlphaGenome
                predictions = self.client.predict_variant_effects(
                    chrom=chrom,
                    pos=pos,
                    ref=ref,
                    alt=alt,
                    sequence_context=context_info['sequence'],
                    predictions=self.predictions
                )
                
                results[alt] = predictions
                
            except SequenceError as e:
                logging.error(f"Sequence error for {chrom}:{pos} {ref}>{alt}: {e}")
                self.stats['sequence_errors'] += 1
                continue
                
            except (AlphaGenomeAPIError, RateLimitError) as e:
                logging.error(f"API error for {chrom}:{pos} {ref}>{alt}: {e}")
                self.stats['api_errors'] += 1
                continue
                
            except Exception as e:
                logging.error(f"Unexpected error for {chrom}:{pos} {ref}>{alt}: {e}")
                self.stats['api_errors'] += 1
                continue
                
        return results if results else None
        
    def add_info_headers(self, vcf_reader):
        """Add AlphaGenome INFO field headers to VCF."""
        info_fields = {
            'expression': ('AG_EXPR', 'A', 'Float', 'AlphaGenome expression impact score (0-1)'),
            'splicing': ('AG_SPLICE', 'A', 'Float', 'AlphaGenome splicing impact score (0-1)'),
            'chromatin': ('AG_CHROM', 'A', 'Float', 'AlphaGenome chromatin impact score (0-1)'),
            'conservation': ('AG_CONS', 'A', 'Float', 'AlphaGenome conservation score (0-1)')
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
        vcf_reader.add_to_header(f"##AlphaGenomeWindowSize={self.window_size}")
        
    def run(self):
        """Run the variant scoring pipeline."""
        logging.info("Starting AlphaGenome variant scoring")
        logging.info(f"Input VCF: {self.vcf_path}")
        logging.info(f"Reference: {self.reference_path}")
        logging.info(f"Predictions: {', '.join(self.predictions)}")
        logging.info(f"Window size: {self.window_size}")
        logging.info(f"Max variants: {self.max_variants}")
        
        # Open VCF for reading
        try:
            vcf_reader = VCF(self.vcf_path)
        except Exception as e:
            raise ValueError(f"Failed to open VCF file {self.vcf_path}: {e}")
        
        # Add headers
        self.add_info_headers(vcf_reader)
        
        # Open output VCF for writing
        try:
            vcf_writer = Writer(self.output_path, vcf_reader)
        except Exception as e:
            raise ValueError(f"Failed to create output VCF {self.output_path}: {e}")
        
        # Process variants
        try:
            for variant_num, variant in enumerate(vcf_reader):
                self.stats['total_variants'] += 1
                
                # Check variant limit
                if variant_num >= self.max_variants:
                    logging.warning(f"Reached maximum variant limit ({self.max_variants})")
                    # Still write remaining variants without annotation
                    vcf_writer.write_record(variant)
                    continue
                    
                # Progress reporting
                if variant_num % 100 == 0 and variant_num > 0:
                    self._report_progress(variant_num)
                    
                # Process variant
                results = self.process_variant(variant)
                
                if results:
                    # Add predictions to INFO fields
                    self._add_predictions_to_variant(variant, results)
                    self.stats['processed_variants'] += 1
                else:
                    self.stats['skipped_variants'] += 1
                    
                # Write variant (with or without annotations)
                vcf_writer.write_record(variant)
                
        except Exception as e:
            logging.error(f"Error processing variants: {e}")
            raise
            
        finally:
            # Always close files
            vcf_writer.close()
            vcf_reader.close()
            self.sequence_extractor.close()
            
        # Final report
        self._report_final_stats()
        
    def _add_predictions_to_variant(self, variant, results: Dict):
        """Add prediction scores to variant INFO fields."""
        info_mapping = {
            'expression': 'AG_EXPR',
            'splicing': 'AG_SPLICE',
            'chromatin': 'AG_CHROM',
            'conservation': 'AG_CONS'
        }
        
        # Initialize INFO arrays for each prediction type
        for pred_type in self.predictions:
            info_key = info_mapping.get(pred_type)
            if info_key:
                # Initialize with None values for all alleles
                if variant.INFO.get(info_key) is None:
                    variant.INFO[info_key] = [None] * len(variant.ALT)
        
        # Fill in actual scores
        for alt_idx, alt in enumerate(variant.ALT):
            if alt in results:
                predictions = results[alt]
                for pred_type, score in predictions.items():
                    info_key = info_mapping.get(pred_type)
                    if info_key and variant.INFO.get(info_key) is not None:
                        variant.INFO[info_key][alt_idx] = round(float(score), 4)
        
    def _report_progress(self, variant_num: int):
        """Report progress to Galaxy."""
        if self.max_variants > 0:
            progress = (variant_num / self.max_variants) * 100
            print(f"Progress: {progress:.1f}% ({variant_num}/{self.max_variants} variants processed)", 
                  flush=True)
        else:
            print(f"Processed {variant_num} variants", flush=True)
              
    def _report_final_stats(self):
        """Report final statistics."""
        logging.info("=" * 50)
        logging.info("ALPHAGENOME VARIANT SCORER - FINAL STATISTICS")
        logging.info("=" * 50)
        logging.info(f"Total variants: {self.stats['total_variants']}")
        logging.info(f"Processed variants: {self.stats['processed_variants']}")
        logging.info(f"Skipped variants: {self.stats['skipped_variants']}")
        logging.info(f"Multiallelic variants: {self.stats['multiallelic_variants']}")
        logging.info(f"API errors: {self.stats['api_errors']}")
        logging.info(f"Sequence errors: {self.stats['sequence_errors']}")
        
        # Client statistics
        client_stats = self.client.get_stats()
        logging.info(f"API calls made: {client_stats['api_calls']}")
        logging.info(f"Cache hits: {client_stats['cache_hits']}")
        logging.info(f"Cache hit rate: {client_stats['cache_hit_rate']:.1f}%")
        
        # Cache statistics
        if self.cache_manager:
            cache_stats = self.cache_manager.get_stats()
            logging.info(f"Cache size: {cache_stats['total_items']} items ({cache_stats['total_size_mb']} MB)")
            
        # Success rate
        if self.stats['total_variants'] > 0:
            success_rate = (self.stats['processed_variants'] / self.stats['total_variants']) * 100
            logging.info(f"Success rate: {success_rate:.1f}%")


def setup_logging(verbose: bool = False):
    """Configure logging for Galaxy tool."""
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(sys.stderr)
        ]
    )


def validate_inputs(args):
    """Validate all input arguments."""
    # Check required files exist
    if not os.path.exists(args.input):
        raise FileNotFoundError(f"Input VCF file not found: {args.input}")
        
    if not os.path.exists(args.reference):
        raise FileNotFoundError(f"Reference genome file not found: {args.reference}")
    
    # Check API key is provided
    if not args.api_key or args.api_key.strip() == "":
        raise ValueError("AlphaGenome API key is required")
    
    # Validate prediction types
    valid_predictions = {'expression', 'splicing', 'chromatin', 'conservation'}
    invalid_predictions = set(args.predictions) - valid_predictions
    if invalid_predictions:
        raise ValueError(f"Invalid prediction types: {invalid_predictions}")
    
    # Validate numeric parameters
    if args.max_variants <= 0:
        raise ValueError("max_variants must be positive")
        
    if args.window_size <= 0:
        raise ValueError("window_size must be positive")


def parse_arguments():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Score genetic variants using AlphaGenome predictions",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s -i variants.vcf -o scored.vcf -r genome.fa -k API_KEY
  %(prog)s -i variants.vcf -o scored.vcf -r genome.fa -k API_KEY -p expression splicing
        """
    )
    
    # Required arguments
    parser.add_argument('--input', '-i', required=True,
                       help='Input VCF file')
    parser.add_argument('--output', '-o', required=True,
                       help='Output VCF file')
    parser.add_argument('--reference', '-r', required=True,
                       help='Reference genome (FASTA)')
    parser.add_argument('--api-key', '-k', required=True,
                       help='AlphaGenome API key')
    
    # Prediction options
    parser.add_argument('--predictions', '-p', nargs='+',
                       choices=['expression', 'splicing', 'chromatin', 'conservation'],
                       default=['expression', 'splicing'],
                       help='Types of predictions to include (default: expression splicing)')
    
    # Processing options
    parser.add_argument('--max-variants', type=int, default=1000,
                       help='Maximum number of variants to process (default: 1000)')
    parser.add_argument('--window-size', type=int, default=1000,
                       help='Sequence context window size (default: 1000)')
    parser.add_argument('--batch-size', type=int, default=50,
                       help='Batch size for API calls (default: 50)')
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
        validate_inputs(args)
        
        # Create cache directory if not provided
        cache_dir = args.cache_dir
        if not cache_dir:
            cache_dir = os.environ.get('TMPDIR', '/tmp')
            cache_dir = os.path.join(cache_dir, 'alphagenome_cache')
            os.makedirs(cache_dir, exist_ok=True)
            
        # Create scorer and run
        scorer = VariantScorer(
            vcf_path=args.input,
            reference_path=args.reference,
            output_path=args.output,
            api_key=args.api_key,
            predictions=args.predictions,
            window_size=args.window_size,
            max_variants=args.max_variants,
            cache_dir=cache_dir,
            batch_size=args.batch_size
        )
        
        scorer.run()
        
        logging.info(f"Successfully wrote annotated VCF to: {args.output}")
        
    except KeyboardInterrupt:
        logging.error("Process interrupted by user")
        sys.exit(130)
        
    except Exception as e:
        logging.error(f"Fatal error: {e}")
        if args.verbose:
            logging.exception("Detailed error information:")
        sys.exit(1)


if __name__ == '__main__':
    main()