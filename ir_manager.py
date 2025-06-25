"""IR signal processing manager for Picomote IR

Handles IR signal reception, decoding, and mapping with efficient caching.
"""

import time
from config import HAS_IRREMOTE

if HAS_IRREMOTE:
    import adafruit_irremote

class IRManager:
    """Manages IR signal processing with debouncing and mapping cache"""
    
    def __init__(self, pulsein, decoder=None, cache_size=10):
        """
        Initialize IR manager with pulse input and decoder
        
        Args:
            pulsein: PulseIn object for IR signal reception
            decoder: IR decoder (default: GenericDecode if available)
            cache_size: Maximum number of cached mappings
        """
        self.pulsein = pulsein
        self.decoder = decoder or (adafruit_irremote.GenericDecode() if HAS_IRREMOTE else None)
        self.last_code_time = 0
        self.last_code = None
        self.debounce_time = 0.1  # 100ms debounce for repeat signals
        
        self.mapping_cache = {}
        self.cache_usage_count = {}
        self.cache_access_time = {}
        self.max_cache_size = cache_size
        
        self.cache_hits = 0
        self.cache_misses = 0
        self.total_lookups = 0
    
    def get_ir_code(self):
        """
        Process IR signals and return decoded code with built-in debouncing
        
        Returns:
            int or None: IR code if valid signal detected, None otherwise
        """
        if not self.pulsein or not self.decoder or len(self.pulsein) == 0:
            return None
            
        current_time = time.monotonic()
        
        try:
            pulses = self.decoder.read_pulses(self.pulsein, blocking=False)
            if not pulses or len(pulses) < 8:
                return None

            code_values = self.decoder.decode_bits(pulses)

            if len(code_values) >= 4:
                ir_code = 0
                for byte_val in code_values[:4]:
                    ir_code = (ir_code << 8) | byte_val

                # Debouncing: ignore same code within debounce window
                if (ir_code == self.last_code and 
                    current_time - self.last_code_time < self.debounce_time):
                    return None
                
                self.last_code = ir_code
                self.last_code_time = current_time
                
                return ir_code
            else:
                return None

        except adafruit_irremote.IRNECRepeatException:
            # Handle repeat signals - return last code if within reasonable time
            if (self.last_code and 
                current_time - self.last_code_time < 0.5):  # 500ms repeat window
                return self.last_code
            return None
            
        except Exception:
            pass
            
        finally:
            # Always clear the buffer
            if self.pulsein:
                try:
                    self.pulsein.clear()
                except:
                    pass
                    
        return None
    
    def lookup_mapping(self, ir_code, full_mappings):
        """
        Fast lookup of IR code mapping with intelligent caching
        
        Args:
            ir_code: IR code to lookup
            full_mappings: Complete mappings dictionary
            
        Returns:
            str or None: Mapped key name if found, None otherwise
        """
        self.total_lookups += 1
        current_time = time.monotonic()
        
        # Check cache first
        if ir_code in self.mapping_cache:
            self.cache_hits += 1
            self.cache_usage_count[ir_code] = self.cache_usage_count.get(ir_code, 0) + 1
            self.cache_access_time[ir_code] = current_time
            return self.mapping_cache[ir_code]
        
        # Cache miss - lookup in full mappings
        self.cache_misses += 1
        
        if ir_code in full_mappings:
            key_name = full_mappings[ir_code]
            
            # Add to cache if there's space
            if len(self.mapping_cache) < self.max_cache_size:
                self.mapping_cache[ir_code] = key_name
                self.cache_usage_count[ir_code] = 1
                self.cache_access_time[ir_code] = current_time
            else:
                # Cache is full - evict least recently used item
                self._evict_lru_item()
                self.mapping_cache[ir_code] = key_name
                self.cache_usage_count[ir_code] = 1
                self.cache_access_time[ir_code] = current_time
            
            return key_name
        
        return None
    
    def _evict_lru_item(self):
        """Evict the least recently used item from cache"""
        if not self.cache_access_time:
            return
            
        # Find item with oldest access time
        oldest_code = min(self.cache_access_time.keys(), 
                         key=lambda k: self.cache_access_time[k])
        
        # Remove from all cache structures
        del self.mapping_cache[oldest_code]
        del self.cache_usage_count[oldest_code]
        del self.cache_access_time[oldest_code]
    
    def preload_frequent_mappings(self, mappings, max_preload=5):
        """
        Preload frequently used mappings into cache
        
        Args:
            mappings: Full mappings dictionary
            max_preload: Maximum number of mappings to preload
        """
        if not mappings:
            return
            
        preload_count = min(max_preload, len(mappings), self.max_cache_size)
        
        for i, (ir_code, key_name) in enumerate(mappings.items()):
            if i >= preload_count:
                break
                
            self.mapping_cache[ir_code] = key_name
            self.cache_usage_count[ir_code] = 0
            self.cache_access_time[ir_code] = time.monotonic()
    
    def get_cache_stats(self):
        """
        Get cache performance statistics
        
        Returns:
            dict: Cache statistics
        """
        hit_rate = (self.cache_hits / self.total_lookups * 100) if self.total_lookups > 0 else 0.0
        return {
            'cache_size': len(self.mapping_cache),
            'max_cache_size': self.max_cache_size,
            'total_lookups': self.total_lookups,
            'cache_hits': self.cache_hits,
            'cache_misses': self.cache_misses,
            'hit_rate_percent': hit_rate
        }
    
    def clear_cache(self):
        """Clear the mapping cache"""
        self.mapping_cache.clear()
        self.cache_usage_count.clear()
        self.cache_access_time.clear()
    
    def clear_buffer(self):
        """Clear the IR input buffer"""
        if self.pulsein:
            try:
                self.pulsein.clear()
            except:
                pass
    
    def reset_debounce(self):
        """Reset debounce state - useful when entering learning mode"""
        self.last_code = None
        self.last_code_time = 0 