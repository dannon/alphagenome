#!/usr/bin/env python
"""
Sequence utilities for AlphaGenome Galaxy tools.

Provides utilities for extracting genomic sequences, validation,
and coordinate system conversions.
"""

import logging
import re
from typing import Tuple, Optional, Dict, List
import pysam


class SequenceError(Exception):
    """Custom exception for sequence-related errors."""
    pass


class SequenceExtractor:
    """
    Extract genomic sequences with proper error handling and validation.
    
    Handles coordinate systems, edge cases, and provides caching for
    frequently accessed sequences.
    """
    
    def __init__(self, reference_path: str):
        """
        Initialize sequence extractor.
        
        Args:
            reference_path: Path to reference FASTA file
        """
        self.reference_path = reference_path
        self.reference = None
        self._chromosome_cache = {}
        self._sequence_cache = {}
        
        try:
            self.reference = pysam.FastaFile(reference_path)
            self._load_chromosome_info()
        except Exception as e:
            raise SequenceError(f"Failed to open reference file {reference_path}: {e}")
            
    def _load_chromosome_info(self):
        """Load chromosome information for validation."""
        try:
            for chrom in self.reference.references:
                length = self.reference.get_reference_length(chrom)
                self._chromosome_cache[chrom] = {
                    'length': length,
                    'valid': True
                }
                
                # Also cache common chromosome name variants
                chrom_variants = self._get_chromosome_variants(chrom)
                for variant in chrom_variants:
                    if variant != chrom:
                        self._chromosome_cache[variant] = {
                            'length': length,
                            'valid': True,
                            'canonical': chrom
                        }
                        
        except Exception as e:
            logging.warning(f"Failed to load chromosome info: {e}")
            
    def _get_chromosome_variants(self, chrom: str) -> List[str]:
        """Get common variants of chromosome names."""
        variants = [chrom]
        
        # Handle chr prefix variants
        if chrom.startswith('chr'):
            variants.append(chrom[3:])
        else:
            variants.append(f'chr{chrom}')
            
        # Handle chromosome aliases
        aliases = {
            '23': ['X', 'chrX'],
            '24': ['Y', 'chrY'],
            '25': ['M', 'MT', 'chrM', 'chrMT'],
            'X': ['23', 'chr23'],
            'Y': ['24', 'chr24'],
            'M': ['25', 'MT', 'chr25', 'chrMT'],
            'MT': ['25', 'M', 'chr25', 'chrM']
        }
        
        chrom_clean = chrom.replace('chr', '')
        if chrom_clean in aliases:
            variants.extend(aliases[chrom_clean])
            
        return list(set(variants))
        
    def _normalize_chromosome(self, chrom: str) -> str:
        """Normalize chromosome name to match reference."""
        if chrom in self._chromosome_cache:
            canonical = self._chromosome_cache[chrom].get('canonical', chrom)
            return canonical
            
        # Try variants
        variants = self._get_chromosome_variants(chrom)
        for variant in variants:
            if variant in self._chromosome_cache:
                canonical = self._chromosome_cache[variant].get('canonical', variant)
                return canonical
                
        raise SequenceError(f"Chromosome '{chrom}' not found in reference")
        
    def validate_coordinates(self, chrom: str, start: int, end: int) -> Tuple[bool, str]:
        """
        Validate genomic coordinates.
        
        Args:
            chrom: Chromosome name
            start: Start position (0-based)
            end: End position (0-based, exclusive)
            
        Returns:
            Tuple of (is_valid, error_message)
        """
        try:
            # Normalize chromosome name
            norm_chrom = self._normalize_chromosome(chrom)
            
            # Check if chromosome exists
            if norm_chrom not in self._chromosome_cache:
                return False, f"Chromosome '{chrom}' not found in reference"
                
            chrom_length = self._chromosome_cache[norm_chrom]['length']
            
            # Validate coordinates
            if start < 0:
                return False, f"Start position {start} is negative"
            if end <= start:
                return False, f"End position {end} must be greater than start {start}"
            if start >= chrom_length:
                return False, f"Start position {start} exceeds chromosome length {chrom_length}"
            if end > chrom_length:
                return False, f"End position {end} exceeds chromosome length {chrom_length}"
                
            return True, ""
            
        except Exception as e:
            return False, str(e)
            
    def extract_sequence(self, 
                        chrom: str, 
                        start: int, 
                        end: int,
                        cache: bool = True) -> str:
        """
        Extract sequence from reference genome.
        
        Args:
            chrom: Chromosome name
            start: Start position (0-based)
            end: End position (0-based, exclusive)
            cache: Whether to cache the result
            
        Returns:
            DNA sequence string
            
        Raises:
            SequenceError: If coordinates are invalid or extraction fails
        """
        # Generate cache key
        cache_key = f"{chrom}:{start}-{end}"
        
        # Check cache first
        if cache and cache_key in self._sequence_cache:
            return self._sequence_cache[cache_key]
            
        # Validate coordinates
        is_valid, error_msg = self.validate_coordinates(chrom, start, end)
        if not is_valid:
            raise SequenceError(error_msg)
            
        try:
            # Normalize chromosome name
            norm_chrom = self._normalize_chromosome(chrom)
            
            # Extract sequence
            sequence = self.reference.fetch(norm_chrom, start, end)
            
            # Validate sequence
            if not sequence:
                raise SequenceError(f"No sequence returned for {chrom}:{start}-{end}")
                
            # Cache result
            if cache:
                self._sequence_cache[cache_key] = sequence
                
            return sequence.upper()
            
        except Exception as e:
            raise SequenceError(f"Failed to extract sequence for {chrom}:{start}-{end}: {e}")
            
    def extract_variant_context(self,
                               chrom: str,
                               pos: int,
                               ref: str,
                               alt: str,
                               window_size: int = 1000) -> Dict[str, any]:
        """
        Extract sequence context around a variant.
        
        Args:
            chrom: Chromosome name
            pos: Position (1-based VCF coordinates)
            ref: Reference allele
            alt: Alternate allele
            window_size: Size of sequence window to extract
            
        Returns:
            Dictionary with sequence context and variant information
        """
        # Convert to 0-based coordinates
        pos_0based = pos - 1
        
        # Calculate window boundaries
        half_window = window_size // 2
        start = max(0, pos_0based - half_window)
        end = pos_0based + half_window
        
        # Adjust window if near chromosome boundaries
        try:
            norm_chrom = self._normalize_chromosome(chrom)
            chrom_length = self._chromosome_cache[norm_chrom]['length']
            
            if end > chrom_length:
                end = chrom_length
                start = max(0, end - window_size)
                
        except Exception:
            # If we can't get chromosome length, proceed with original boundaries
            pass
            
        # Extract sequence
        sequence = self.extract_sequence(chrom, start, end)
        
        # Calculate variant position within the extracted sequence
        variant_pos_in_seq = pos_0based - start
        
        # Validate reference allele matches
        actual_ref = sequence[variant_pos_in_seq:variant_pos_in_seq + len(ref)]
        if actual_ref.upper() != ref.upper():
            logging.warning(
                f"Reference mismatch at {chrom}:{pos}: "
                f"expected {ref}, found {actual_ref}"
            )
            
        return {
            'sequence': sequence,
            'variant_pos': variant_pos_in_seq,
            'window_start': start,
            'window_end': end,
            'actual_ref': actual_ref,
            'ref_matches': actual_ref.upper() == ref.upper()
        }
        
    def close(self):
        """Close the reference file."""
        if self.reference:
            self.reference.close()
            
    def __enter__(self):
        """Context manager entry."""
        return self
        
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.close()


def validate_dna_sequence(sequence: str) -> Tuple[bool, str]:
    """
    Validate DNA sequence.
    
    Args:
        sequence: DNA sequence string
        
    Returns:
        Tuple of (is_valid, error_message)
    """
    if not sequence:
        return False, "Empty sequence"
        
    # Check for valid DNA characters
    valid_chars = set('ACGTNacgtn')
    invalid_chars = set(sequence) - valid_chars
    
    if invalid_chars:
        return False, f"Invalid characters found: {sorted(invalid_chars)}"
        
    # Check for excessive N content
    n_count = sequence.upper().count('N')
    n_percentage = (n_count / len(sequence)) * 100
    
    if n_percentage > 50:
        return False, f"Excessive N content: {n_percentage:.1f}%"
        
    return True, ""


def reverse_complement(sequence: str) -> str:
    """
    Get reverse complement of DNA sequence.
    
    Args:
        sequence: DNA sequence string
        
    Returns:
        Reverse complement sequence
    """
    complement_map = {
        'A': 'T', 'T': 'A', 'C': 'G', 'G': 'C',
        'a': 't', 't': 'a', 'c': 'g', 'g': 'c',
        'N': 'N', 'n': 'n'
    }
    
    complement = ''.join(complement_map.get(base, base) for base in sequence)
    return complement[::-1]


def vcf_to_0based(vcf_pos: int) -> int:
    """Convert VCF 1-based position to 0-based."""
    return vcf_pos - 1


def bed_to_vcf_pos(bed_start: int) -> int:
    """Convert BED 0-based start to VCF 1-based position."""
    return bed_start + 1