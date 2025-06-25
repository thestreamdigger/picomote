"""Display caching system for Picomote IR

Provides efficient caching for display elements to reduce memory usage
and improve performance when updating the OLED display.
"""

import displayio
import terminalio

try:
    from adafruit_display_text import label
    HAS_DISPLAY_TEXT = True
except ImportError:
    HAS_DISPLAY_TEXT = False

class DisplayCache:
    """Manages display group caching to reduce recreation overhead"""
    
    def __init__(self, max_cache_size=5):
        """
        Initialize display cache
        
        Args:
            max_cache_size: Maximum number of cached display groups
        """
        self.cached_groups = {}
        self.last_values = {}
        self.max_cache_size = max_cache_size
        self.cache_hits = 0
        self.cache_misses = 0
    
    def get_or_create(self, cache_key, builder_func, *args, **kwargs):
        """
        Get cached display group or create new one using builder function
        
        Args:
            cache_key: Unique identifier for this display state
            builder_func: Function to build the display group
            *args, **kwargs: Arguments passed to builder_func
            
        Returns:
            displayio.Group: Display group ready for use
        """
        if cache_key in self.cached_groups:
            self.cache_hits += 1
            return self.cached_groups[cache_key]
        
        self.cache_misses += 1
        
        try:
            new_group = builder_func(*args, **kwargs)
            
            if len(self.cached_groups) >= self.max_cache_size:
                oldest_key = next(iter(self.cached_groups))
                del self.cached_groups[oldest_key]
                if oldest_key in self.last_values:
                    del self.last_values[oldest_key]
            
            self.cached_groups[cache_key] = new_group
            return new_group
            
        except:
            return displayio.Group()
    
    def invalidate(self, cache_key=None):
        """
        Invalidate cache entries
        
        Args:
            cache_key: Specific key to invalidate. If None, clears all
        """
        if cache_key is None:
            self.cached_groups.clear()
            self.last_values.clear()
        elif cache_key in self.cached_groups:
            del self.cached_groups[cache_key]
            if cache_key in self.last_values:
                del self.last_values[cache_key]
    
    def has_changed(self, cache_key, current_value):
        """
        Check if a value has changed since last cache
        
        Args:
            cache_key: Cache key to check
            current_value: Current value to compare
            
        Returns:
            bool: True if value has changed or is new
        """
        if cache_key not in self.last_values:
            self.last_values[cache_key] = current_value
            return True
            
        if self.last_values[cache_key] != current_value:
            self.last_values[cache_key] = current_value
            return True
            
        return False
    
    def get_stats(self):
        """
        Get cache performance statistics
        
        Returns:
            dict: Cache statistics
        """
        total_requests = self.cache_hits + self.cache_misses
        hit_rate = (self.cache_hits / total_requests * 100) if total_requests > 0 else 0
        
        return {
            'cache_size': len(self.cached_groups),
            'max_size': self.max_cache_size,
            'hits': self.cache_hits,
            'misses': self.cache_misses,
            'hit_rate': hit_rate
        }
    
    def create_text_group(self, lines, colors=None, positions=None, font=None):
        """
        Helper method to create a text-based display group
        
        Args:
            lines: List of text strings
            colors: List of colors for each line
            positions: List of (x, y) positions for each line
            font: Font to use (defaults to terminalio.FONT)
            
        Returns:
            displayio.Group: Group with text labels
        """
        if not HAS_DISPLAY_TEXT:
            return displayio.Group()
            
        group = displayio.Group()
        font = font or terminalio.FONT
        
        for i, line in enumerate(lines):
            color = colors[i] if colors and i < len(colors) else 0xFFFFFF
            
            if positions and i < len(positions):
                x, y = positions[i]
            else:
                x, y = 0, 10 + (i * 16)
            
            text_label = label.Label(font, text=str(line), color=color, x=x, y=y)
            group.append(text_label)
        
        return group 