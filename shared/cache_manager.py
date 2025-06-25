#!/usr/bin/env python
"""
Cache Manager for AlphaGenome API results.

Provides persistent caching of API results to minimize redundant calls
and improve performance.
"""

import json
import logging
import shutil
import time
from pathlib import Path
from typing import Dict, Optional, Any
import hashlib


class CacheManager:
    """
    Manage persistent caching of AlphaGenome API results.
    
    Features:
    - Hierarchical directory structure to avoid too many files in one directory
    - TTL (time-to-live) support for cache expiration
    - Cache statistics and management
    - Safe file operations with atomic writes
    """
    
    def __init__(self, 
                 cache_dir: str,
                 default_ttl: int = 7 * 24 * 3600,  # 7 days
                 max_cache_size: int = 1000):  # Max number of cached items
        """
        Initialize cache manager.
        
        Args:
            cache_dir: Directory to store cache files
            default_ttl: Default time-to-live in seconds
            max_cache_size: Maximum number of items to cache
        """
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.default_ttl = default_ttl
        self.max_cache_size = max_cache_size
        
        # Initialize cache metadata
        self.metadata_file = self.cache_dir / "cache_metadata.json"
        self.metadata = self._load_metadata()
        
        # Statistics
        self.stats = {
            'hits': 0,
            'misses': 0,
            'sets': 0,
            'expires': 0,
            'evictions': 0
        }
        
    def _load_metadata(self) -> Dict:
        """Load cache metadata from disk."""
        if self.metadata_file.exists():
            try:
                with open(self.metadata_file, 'r') as f:
                    return json.load(f)
            except (json.JSONDecodeError, IOError):
                logging.warning("Invalid cache metadata file, starting fresh")
                
        return {
            'items': {},
            'created': time.time(),
            'version': '1.0'
        }
        
    def _save_metadata(self):
        """Save cache metadata to disk."""
        try:
            # Atomic write using temporary file
            temp_file = self.metadata_file.with_suffix('.tmp')
            with open(temp_file, 'w') as f:
                json.dump(self.metadata, f, indent=2)
            temp_file.replace(self.metadata_file)
        except IOError as e:
            logging.error(f"Failed to save cache metadata: {e}")
            
    def _get_cache_path(self, key: str) -> Path:
        """
        Get cache file path for a given key.
        
        Uses first 2 characters of key for subdirectory to avoid
        too many files in one directory.
        """
        # Create subdirectory based on first 2 chars of key
        subdir = self.cache_dir / key[:2]
        subdir.mkdir(exist_ok=True)
        
        # Use safe filename
        safe_key = key.replace('/', '_').replace('\\', '_')
        return subdir / f"{safe_key}.json"
        
    def _is_expired(self, key: str) -> bool:
        """Check if cache entry is expired."""
        if key not in self.metadata['items']:
            return True
            
        item_info = self.metadata['items'][key]
        ttl = item_info.get('ttl', self.default_ttl)
        created_time = item_info.get('created', 0)
        
        return time.time() - created_time > ttl
        
    def _cleanup_expired(self):
        """Remove expired cache entries."""
        expired_keys = []
        
        for key in self.metadata['items']:
            if self._is_expired(key):
                expired_keys.append(key)
                
        for key in expired_keys:
            self._remove_item(key)
            self.stats['expires'] += 1
            
    def _remove_item(self, key: str):
        """Remove a cache item."""
        # Remove file
        cache_file = self._get_cache_path(key)
        if cache_file.exists():
            cache_file.unlink()
            
        # Remove from metadata
        if key in self.metadata['items']:
            del self.metadata['items'][key]
            
    def _evict_oldest(self):
        """Evict oldest cache entries to make room."""
        if len(self.metadata['items']) <= self.max_cache_size:
            return
            
        # Sort by creation time
        items_by_age = sorted(
            self.metadata['items'].items(),
            key=lambda x: x[1].get('created', 0)
        )
        
        # Remove oldest items
        num_to_remove = len(self.metadata['items']) - self.max_cache_size + 1
        for key, _ in items_by_age[:num_to_remove]:
            self._remove_item(key)
            self.stats['evictions'] += 1
            
    def get(self, key: str) -> Optional[Dict]:
        """
        Retrieve item from cache.
        
        Args:
            key: Cache key
            
        Returns:
            Cached data or None if not found/expired
        """
        # Check if expired
        if self._is_expired(key):
            self.stats['misses'] += 1
            return None
            
        # Try to load from file
        cache_file = self._get_cache_path(key)
        if not cache_file.exists():
            self.stats['misses'] += 1
            return None
            
        try:
            with open(cache_file, 'r') as f:
                data = json.load(f)
                
            # Update access time
            if key in self.metadata['items']:
                self.metadata['items'][key]['last_accessed'] = time.time()
                
            self.stats['hits'] += 1
            return data
            
        except (json.JSONDecodeError, IOError) as e:
            logging.warning(f"Failed to read cache file {cache_file}: {e}")
            # Remove corrupted file
            cache_file.unlink()
            if key in self.metadata['items']:
                del self.metadata['items'][key]
            self.stats['misses'] += 1
            return None
            
    def set(self, key: str, value: Dict, ttl: Optional[int] = None):
        """
        Store item in cache.
        
        Args:
            key: Cache key
            value: Data to cache
            ttl: Time-to-live in seconds (optional)
        """
        # Cleanup expired entries periodically
        if len(self.metadata['items']) % 100 == 0:
            self._cleanup_expired()
            
        # Evict oldest entries if needed
        self._evict_oldest()
        
        # Write cache file
        cache_file = self._get_cache_path(key)
        try:
            # Atomic write using temporary file
            temp_file = cache_file.with_suffix('.tmp')
            with open(temp_file, 'w') as f:
                json.dump(value, f, separators=(',', ':'))
            temp_file.replace(cache_file)
            
            # Update metadata
            self.metadata['items'][key] = {
                'created': time.time(),
                'last_accessed': time.time(),
                'ttl': ttl or self.default_ttl,
                'size': cache_file.stat().st_size
            }
            
            self.stats['sets'] += 1
            
            # Save metadata periodically
            if self.stats['sets'] % 10 == 0:
                self._save_metadata()
                
        except IOError as e:
            logging.error(f"Failed to write cache file {cache_file}: {e}")
            
    def exists(self, key: str) -> bool:
        """Check if key exists in cache and is not expired."""
        return not self._is_expired(key) and self._get_cache_path(key).exists()
        
    def clear(self):
        """Clear all cache entries."""
        try:
            # Remove all cache files
            for cache_file in self.cache_dir.rglob("*.json"):
                if cache_file != self.metadata_file:
                    cache_file.unlink()
                    
            # Remove subdirectories
            for subdir in self.cache_dir.iterdir():
                if subdir.is_dir():
                    shutil.rmtree(subdir)
                    
            # Reset metadata
            self.metadata = {
                'items': {},
                'created': time.time(),
                'version': '1.0'
            }
            self._save_metadata()
            
            logging.info("Cache cleared successfully")
            
        except Exception as e:
            logging.error(f"Failed to clear cache: {e}")
            
    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        total_requests = self.stats['hits'] + self.stats['misses']
        hit_rate = (self.stats['hits'] / total_requests * 100) if total_requests > 0 else 0
        
        # Calculate total cache size
        total_size = 0
        item_count = 0
        for item_info in self.metadata['items'].values():
            total_size += item_info.get('size', 0)
            item_count += 1
            
        return {
            'hits': self.stats['hits'],
            'misses': self.stats['misses'],
            'hit_rate': round(hit_rate, 1),
            'total_items': item_count,
            'total_size_bytes': total_size,
            'total_size_mb': round(total_size / (1024 * 1024), 2),
            'expires': self.stats['expires'],
            'evictions': self.stats['evictions']
        }
        
    def cleanup(self):
        """Perform cache cleanup and maintenance."""
        self._cleanup_expired()
        self._save_metadata()
        logging.info("Cache cleanup completed")
        
    def __del__(self):
        """Ensure metadata is saved when object is destroyed."""
        try:
            self._save_metadata()
        except:
            pass  # Ignore errors during cleanup