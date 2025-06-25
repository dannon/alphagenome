#!/usr/bin/env python
"""
Unit tests for AlphaGenome shared utilities.
"""

import tempfile
import unittest
from pathlib import Path
import sys
import os

# Add shared directory to path
sys.path.insert(0, str(Path(__file__).parent / "shared"))

from cache_manager import CacheManager
from sequence_utils import validate_dna_sequence, reverse_complement
from alphagenome_client import AlphaGenomeClient


class TestCacheManager(unittest.TestCase):
    """Test cache manager functionality."""
    
    def setUp(self):
        """Set up test cache directory."""
        self.temp_dir = tempfile.mkdtemp()
        self.cache = CacheManager(self.temp_dir)
        
    def tearDown(self):
        """Clean up test cache directory."""
        import shutil
        shutil.rmtree(self.temp_dir)
        
    def test_cache_set_get(self):
        """Test basic cache set and get operations."""
        test_key = "test_key"
        test_value = {"score": 0.85, "type": "expression"}
        
        # Set value
        self.cache.set(test_key, test_value)
        
        # Get value
        retrieved = self.cache.get(test_key)
        self.assertEqual(retrieved, test_value)
        
    def test_cache_miss(self):
        """Test cache miss behavior."""
        result = self.cache.get("nonexistent_key")
        self.assertIsNone(result)
        
    def test_cache_stats(self):
        """Test cache statistics."""
        stats = self.cache.get_stats()
        self.assertIn('hits', stats)
        self.assertIn('misses', stats)
        self.assertIn('total_items', stats)


class TestSequenceUtils(unittest.TestCase):
    """Test sequence utility functions."""
    
    def test_validate_dna_sequence_valid(self):
        """Test validation of valid DNA sequences."""
        valid_seqs = ["ATCG", "atcg", "NNNATCGNN", ""]
        
        for seq in valid_seqs:
            is_valid, msg = validate_dna_sequence(seq)
            if seq:  # Non-empty sequences should be valid
                self.assertTrue(is_valid, f"Sequence {seq} should be valid: {msg}")
            else:  # Empty sequence should be invalid
                self.assertFalse(is_valid)
                
    def test_validate_dna_sequence_invalid(self):
        """Test validation of invalid DNA sequences."""
        invalid_seqs = ["ATCGX", "123", "ATCG-", "A B C"]
        
        for seq in invalid_seqs:
            is_valid, msg = validate_dna_sequence(seq)
            self.assertFalse(is_valid, f"Sequence {seq} should be invalid")
            
    def test_reverse_complement(self):
        """Test reverse complement function."""
        test_cases = [
            ("A", "T"),
            ("T", "A"), 
            ("C", "G"),
            ("G", "C"),
            ("ATCG", "CGAT"),
            ("atcg", "cgat"),
            ("NNNN", "NNNN")
        ]
        
        for seq, expected in test_cases:
            result = reverse_complement(seq)
            self.assertEqual(result, expected, 
                           f"Reverse complement of {seq} should be {expected}, got {result}")


class TestAlphaGenomeClient(unittest.TestCase):
    """Test AlphaGenome API client."""
    
    def setUp(self):
        """Set up test client."""
        # Use a fake API key for testing
        self.client = AlphaGenomeClient("test_api_key_123")
        
    def test_client_initialization(self):
        """Test client initialization."""
        self.assertEqual(self.client.api_key, "test_api_key_123")
        self.assertIsNotNone(self.client.session)
        self.assertEqual(self.client.rate_limit_delay, 0.1)
        
    def test_rate_limiting(self):
        """Test rate limiting functionality."""
        import time
        
        start_time = time.time()
        self.client._rate_limit()
        first_call_time = time.time()
        
        # Second call should be delayed
        self.client._rate_limit()
        second_call_time = time.time()
        
        # Should have at least some delay
        delay = second_call_time - first_call_time
        self.assertGreaterEqual(delay, 0.05)  # Allow some tolerance
        
    def test_cache_key_generation(self):
        """Test cache key generation."""
        key1 = self.client._generate_cache_key(chrom="chr1", pos=100, ref="A", alt="G")
        key2 = self.client._generate_cache_key(chrom="chr1", pos=100, ref="A", alt="G")
        key3 = self.client._generate_cache_key(chrom="chr1", pos=101, ref="A", alt="G")
        
        # Same parameters should generate same key
        self.assertEqual(key1, key2)
        
        # Different parameters should generate different keys
        self.assertNotEqual(key1, key3)
        
    def test_stats_tracking(self):
        """Test statistics tracking."""
        stats = self.client.get_stats()
        
        self.assertIn('api_calls', stats)
        self.assertIn('cache_hits', stats)
        self.assertIn('errors', stats)
        self.assertIn('rate_limits', stats)
        self.assertIn('cache_hit_rate', stats)


if __name__ == '__main__':
    unittest.main()