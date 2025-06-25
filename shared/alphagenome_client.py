#!/usr/bin/env python
"""
AlphaGenome API Client with rate limiting, caching, and error handling.

This module provides a robust interface to the AlphaGenome API with:
- Rate limiting to respect API quotas
- Intelligent caching to minimize API calls
- Comprehensive error handling and retry logic
- Batch processing capabilities
"""

import hashlib
import json
import logging
import time
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry


class AlphaGenomeAPIError(Exception):
    """Custom exception for AlphaGenome API errors."""
    pass


class RateLimitError(AlphaGenomeAPIError):
    """Exception raised when API rate limit is exceeded."""
    pass


class AlphaGenomeClient:
    """
    Robust AlphaGenome API client with caching and rate limiting.
    
    Features:
    - Automatic rate limiting with exponential backoff
    - Persistent caching of API results
    - Batch processing support
    - Comprehensive error handling
    - Request retries with backoff
    """
    
    def __init__(self, 
                 api_key: str,
                 cache_dir: Optional[str] = None,
                 rate_limit_delay: float = 0.1,
                 max_retries: int = 3,
                 timeout: int = 30):
        """
        Initialize AlphaGenome API client.
        
        Args:
            api_key: AlphaGenome API key
            cache_dir: Directory for caching results (optional)
            rate_limit_delay: Minimum delay between API calls in seconds
            max_retries: Maximum number of retry attempts
            timeout: Request timeout in seconds
        """
        self.api_key = api_key
        self.rate_limit_delay = rate_limit_delay
        self.max_retries = max_retries
        self.timeout = timeout
        self.last_request_time = 0
        
        # Initialize cache if directory provided
        self.cache_manager = None
        if cache_dir:
            try:
                from .cache_manager import CacheManager
            except ImportError:
                from cache_manager import CacheManager
            self.cache_manager = CacheManager(cache_dir)
        
        # Setup requests session with retry strategy
        self.session = self._create_session()
        
        # Statistics tracking
        self.stats = {
            'api_calls': 0,
            'cache_hits': 0,
            'errors': 0,
            'rate_limits': 0
        }
        
        # API endpoint (this would be the real AlphaGenome endpoint)
        self.base_url = "https://api.alphagenome.deepmind.com/v1"
        
    def _create_session(self) -> requests.Session:
        """Create requests session with retry strategy."""
        session = requests.Session()
        
        # Define retry strategy
        retry_strategy = Retry(
            total=self.max_retries,
            status_forcelist=[429, 500, 502, 503, 504],
            method_whitelist=["HEAD", "GET", "POST"],
            backoff_factor=1,
            raise_on_status=False
        )
        
        adapter = HTTPAdapter(max_retries=retry_strategy)
        session.mount("http://", adapter)
        session.mount("https://", adapter)
        
        # Set default headers
        session.headers.update({
            'Authorization': f'Bearer {self.api_key}',
            'Content-Type': 'application/json',
            'User-Agent': 'AlphaGenome-Galaxy-Tool/1.0'
        })
        
        return session
        
    def _rate_limit(self):
        """Implement rate limiting between API calls."""
        current_time = time.time()
        time_since_last = current_time - self.last_request_time
        
        if time_since_last < self.rate_limit_delay:
            sleep_time = self.rate_limit_delay - time_since_last
            logging.debug(f"Rate limiting: sleeping for {sleep_time:.3f}s")
            time.sleep(sleep_time)
            
        self.last_request_time = time.time()
        
    def _generate_cache_key(self, **params) -> str:
        """Generate cache key from parameters."""
        # Sort parameters for consistent cache keys
        key_data = json.dumps(params, sort_keys=True)
        return hashlib.md5(key_data.encode()).hexdigest()
        
    def _make_request(self, endpoint: str, data: Dict) -> Dict:
        """
        Make API request with error handling and retries.
        
        Args:
            endpoint: API endpoint
            data: Request payload
            
        Returns:
            API response data
            
        Raises:
            AlphaGenomeAPIError: For API errors
            RateLimitError: For rate limit errors
        """
        url = f"{self.base_url}/{endpoint}"
        
        for attempt in range(self.max_retries + 1):
            try:
                self._rate_limit()
                self.stats['api_calls'] += 1
                
                response = self.session.post(url, json=data, timeout=self.timeout)
                
                if response.status_code == 200:
                    return response.json()
                elif response.status_code == 429:
                    self.stats['rate_limits'] += 1
                    if attempt < self.max_retries:
                        wait_time = (2 ** attempt) * self.rate_limit_delay
                        logging.warning(f"Rate limited, waiting {wait_time:.1f}s")
                        time.sleep(wait_time)
                        continue
                    else:
                        raise RateLimitError("API rate limit exceeded")
                elif response.status_code == 401:
                    raise AlphaGenomeAPIError("Invalid API key")
                elif response.status_code == 400:
                    error_msg = response.json().get('error', 'Bad request')
                    raise AlphaGenomeAPIError(f"Bad request: {error_msg}")
                else:
                    error_msg = f"API error {response.status_code}: {response.text}"
                    if attempt < self.max_retries:
                        logging.warning(f"{error_msg}, retrying...")
                        time.sleep(2 ** attempt)
                        continue
                    else:
                        raise AlphaGenomeAPIError(error_msg)
                        
            except requests.exceptions.RequestException as e:
                self.stats['errors'] += 1
                if attempt < self.max_retries:
                    logging.warning(f"Request failed: {e}, retrying...")
                    time.sleep(2 ** attempt)
                    continue
                else:
                    raise AlphaGenomeAPIError(f"Request failed: {e}")
                    
        raise AlphaGenomeAPIError("Max retries exceeded")
        
    def predict_variant_effects(self,
                              chrom: str,
                              pos: int,
                              ref: str,
                              alt: str,
                              sequence_context: str,
                              predictions: List[str]) -> Dict:
        """
        Predict effects of a single genetic variant.
        
        Args:
            chrom: Chromosome name
            pos: Position (1-based)
            ref: Reference allele
            alt: Alternate allele
            sequence_context: DNA sequence context around variant
            predictions: List of prediction types to include
            
        Returns:
            Dictionary with prediction scores
        """
        # Generate cache key
        cache_key = self._generate_cache_key(
            chrom=chrom,
            pos=pos,
            ref=ref,
            alt=alt,
            sequence=sequence_context,
            predictions=sorted(predictions)
        )
        
        # Check cache first
        if self.cache_manager:
            cached_result = self.cache_manager.get(cache_key)
            if cached_result:
                self.stats['cache_hits'] += 1
                logging.debug(f"Cache hit for variant {chrom}:{pos}")
                return cached_result
        
        # Prepare API request
        request_data = {
            'sequence': sequence_context,
            'variants': [{
                'chromosome': chrom,
                'position': pos,
                'reference': ref,
                'alternate': alt
            }],
            'predictions': predictions
        }
        
        try:
            # Make API call
            response = self._make_request('predict', request_data)
            
            # Extract results for our variant
            if 'variants' in response and response['variants']:
                result = response['variants'][0]['predictions']
            else:
                raise AlphaGenomeAPIError("Unexpected API response format")
            
            # Cache result
            if self.cache_manager:
                self.cache_manager.set(cache_key, result)
                
            return result
            
        except Exception as e:
            self.stats['errors'] += 1
            logging.error(f"API error for variant {chrom}:{pos}: {e}")
            raise
            
    def predict_variants_batch(self,
                              variants: List[Dict],
                              predictions: List[str],
                              batch_size: int = 50) -> List[Dict]:
        """
        Predict effects for multiple variants in batches.
        
        Args:
            variants: List of variant dictionaries with keys:
                     'chrom', 'pos', 'ref', 'alt', 'sequence'
            predictions: List of prediction types
            batch_size: Number of variants per batch
            
        Returns:
            List of prediction results
        """
        results = []
        total_variants = len(variants)
        
        logging.info(f"Processing {total_variants} variants in batches of {batch_size}")
        
        for i in range(0, total_variants, batch_size):
            batch = variants[i:i + batch_size]
            batch_results = []
            
            # Process each variant in batch
            for variant in batch:
                try:
                    result = self.predict_variant_effects(
                        chrom=variant['chrom'],
                        pos=variant['pos'],
                        ref=variant['ref'],
                        alt=variant['alt'],
                        sequence_context=variant['sequence'],
                        predictions=predictions
                    )
                    batch_results.append(result)
                    
                except Exception as e:
                    logging.error(f"Failed to process variant: {e}")
                    # Add empty result to maintain order
                    batch_results.append({})
                    
            results.extend(batch_results)
            
            # Progress reporting
            progress = min(i + batch_size, total_variants) / total_variants * 100
            logging.info(f"Batch progress: {progress:.1f}%")
            
        return results
        
    def get_stats(self) -> Dict[str, int]:
        """Get client statistics."""
        cache_hit_rate = 0
        if self.stats['api_calls'] + self.stats['cache_hits'] > 0:
            cache_hit_rate = self.stats['cache_hits'] / (
                self.stats['api_calls'] + self.stats['cache_hits']
            ) * 100
            
        return {
            **self.stats,
            'cache_hit_rate': round(cache_hit_rate, 1)
        }
        
    def clear_cache(self):
        """Clear all cached results."""
        if self.cache_manager:
            self.cache_manager.clear()
            logging.info("Cache cleared")