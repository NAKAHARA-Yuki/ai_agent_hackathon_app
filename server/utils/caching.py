"""
Advanced caching utilities for the Izatabi travel planning application.
Implements hybrid L1/L2 caching strategy for improved performance.
"""

import asyncio
import pickle
import hashlib
import time
from typing import Optional, Any, Dict, Callable
from functools import wraps
import json
import logging

logger = logging.getLogger(__name__)

class HybridCache:
    """
    Two-level hybrid caching system:
    - L1: In-memory cache for ultra-fast access
    - L2: Redis cache for persistence and cross-instance sharing
    """
    
    def __init__(self, redis_client=None, max_local_size: int = 1000):
        self.redis = redis_client  # Optional Redis client
        self.local_cache: Dict[str, Dict] = {}  # L1 cache with metadata
        self.max_local_size = max_local_size
        
    def _cleanup_local_cache(self):
        """Remove expired entries and maintain size limit"""
        current_time = time.time()
        
        # Remove expired entries
        expired_keys = [
            key for key, data in self.local_cache.items()
            if current_time > data['expires_at']
        ]
        for key in expired_keys:
            del self.local_cache[key]
        
        # Maintain size limit (LRU eviction)
        if len(self.local_cache) > self.max_local_size:
            # Sort by last access time and remove oldest
            sorted_items = sorted(
                self.local_cache.items(), 
                key=lambda x: x[1]['last_access']
            )
            for key, _ in sorted_items[:len(self.local_cache) - self.max_local_size]:
                del self.local_cache[key]
    
    async def get(self, key: str) -> Optional[Any]:
        """Get value from cache, checking L1 first, then L2"""
        current_time = time.time()
        
        # L1 cache check
        if key in self.local_cache:
            cache_data = self.local_cache[key]
            if current_time <= cache_data['expires_at']:
                cache_data['last_access'] = current_time
                cache_data['hit_count'] += 1
                logger.debug(f"L1 cache hit for key: {key}")
                return cache_data['value']
            else:
                # Expired, remove from L1
                del self.local_cache[key]
        
        # L2 cache check (Redis)
        if self.redis:
            try:
                cached = await self.redis.get(key)
                if cached:
                    value = pickle.loads(cached)
                    # Store in L1 for faster future access
                    ttl_remaining = await self.redis.ttl(key)
                    if ttl_remaining > 0:
                        self.local_cache[key] = {
                            'value': value,
                            'expires_at': current_time + ttl_remaining,
                            'last_access': current_time,
                            'hit_count': 1
                        }
                        self._cleanup_local_cache()
                        logger.debug(f"L2 cache hit for key: {key}")
                        return value
            except Exception as e:
                logger.warning(f"Redis cache error for key {key}: {e}")
        
        return None
    
    async def set(self, key: str, value: Any, ttl: int = 300):
        """Set value in both L1 and L2 caches"""
        current_time = time.time()
        
        # Store in L1 cache
        self.local_cache[key] = {
            'value': value,
            'expires_at': current_time + ttl,
            'last_access': current_time,
            'hit_count': 0
        }
        self._cleanup_local_cache()
        
        # Store in L2 cache (Redis)
        if self.redis:
            try:
                await self.redis.setex(key, ttl, pickle.dumps(value))
                logger.debug(f"Cached value for key: {key} (TTL: {ttl}s)")
            except Exception as e:
                logger.warning(f"Failed to cache in Redis for key {key}: {e}")
    
    async def delete(self, key: str):
        """Delete from both caches"""
        if key in self.local_cache:
            del self.local_cache[key]
        
        if self.redis:
            try:
                await self.redis.delete(key)
            except Exception as e:
                logger.warning(f"Failed to delete from Redis for key {key}: {e}")
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """Get cache statistics for monitoring"""
        total_hits = sum(data['hit_count'] for data in self.local_cache.values())
        return {
            'l1_cache_size': len(self.local_cache),
            'l1_cache_hits': total_hits,
            'l1_max_size': self.max_local_size
        }

class CacheKeyGenerator:
    """Generate consistent cache keys for different types of requests"""
    
    @staticmethod
    def user_persona_key(user_id: str) -> str:
        """Cache key for user persona data"""
        return f"persona:user:{user_id}"
    
    @staticmethod
    def travel_plan_key(user_id: str, plan_hash: str) -> str:
        """Cache key for generated travel plans"""
        return f"plan:user:{user_id}:hash:{plan_hash}"
    
    @staticmethod
    def geocoding_key(address: str) -> str:
        """Cache key for geocoding results"""
        address_hash = hashlib.md5(address.lower().encode()).hexdigest()
        return f"geocode:addr:{address_hash}"
    
    @staticmethod
    def ai_response_key(prompt: str, model: str, context_hash: str) -> str:
        """Cache key for AI responses"""
        prompt_hash = hashlib.md5(prompt.encode()).hexdigest()
        return f"ai:model:{model}:prompt:{prompt_hash}:ctx:{context_hash}"
    
    @staticmethod
    def generate_context_hash(context: Dict) -> str:
        """Generate consistent hash for context data"""
        # Sort keys to ensure consistent hashing
        sorted_context = json.dumps(context, sort_keys=True)
        return hashlib.md5(sorted_context.encode()).hexdigest()[:12]

def cache_with_user_context(cache: HybridCache, ttl: int = 300):
    """
    Decorator for caching function results with user context.
    Automatically includes user ID in cache key.
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Extract user context (assuming JWT claims available)
            user_id = kwargs.get('user_id') or 'anonymous'
            
            # Generate cache key
            func_args_hash = hashlib.md5(
                json.dumps([args, kwargs], sort_keys=True, default=str).encode()
            ).hexdigest()[:12]
            cache_key = f"{func.__name__}:user:{user_id}:args:{func_args_hash}"
            
            # Try to get from cache
            cached_result = await cache.get(cache_key)
            if cached_result is not None:
                logger.info(f"Cache hit for {func.__name__} (user: {user_id})")
                return cached_result
            
            # Execute function and cache result
            result = await func(*args, **kwargs) if asyncio.iscoroutinefunction(func) else func(*args, **kwargs)
            await cache.set(cache_key, result, ttl)
            
            logger.info(f"Cached result for {func.__name__} (user: {user_id}, TTL: {ttl}s)")
            return result
        
        return wrapper
    return decorator

class SmartCache:
    """
    Intelligent caching with content-aware TTL and automatic invalidation
    """
    
    def __init__(self, cache: HybridCache):
        self.cache = cache
        self.invalidation_patterns = {}  # Pattern-based invalidation rules
    
    def register_invalidation_pattern(self, pattern: str, related_patterns: list):
        """Register patterns that should be invalidated together"""
        self.invalidation_patterns[pattern] = related_patterns
    
    async def smart_set(self, key: str, value: Any, content_type: str = 'default'):
        """Set with intelligent TTL based on content type"""
        ttl_mapping = {
            'persona': 1800,      # 30 minutes - personas change rarely
            'geocoding': 86400,   # 24 hours - locations are static
            'ai_response': 300,   # 5 minutes - AI responses may vary
            'travel_plan': 600,   # 10 minutes - plans may be refined
            'static_data': 3600,  # 1 hour - questions, hobbies etc.
            'default': 300        # 5 minutes default
        }
        
        ttl = ttl_mapping.get(content_type, ttl_mapping['default'])
        await self.cache.set(key, value, ttl)
        
        logger.debug(f"Smart cached {content_type} content: {key} (TTL: {ttl}s)")
    
    async def invalidate_pattern(self, pattern: str):
        """Invalidate all cache keys matching pattern and related patterns"""
        patterns_to_invalidate = [pattern] + self.invalidation_patterns.get(pattern, [])
        
        for p in patterns_to_invalidate:
            # In a real implementation, you'd iterate through cache keys
            # For now, this is a placeholder for the pattern matching logic
            logger.info(f"Invalidating cache pattern: {p}")

# Example usage and configuration
def setup_caching_system(redis_client=None):
    """Setup the caching system with proper configuration"""
    
    # Initialize hybrid cache
    cache = HybridCache(redis_client=redis_client, max_local_size=1000)
    smart_cache = SmartCache(cache)
    
    # Register invalidation patterns
    smart_cache.register_invalidation_pattern(
        'persona:*', ['plan:*', 'ai:*']  # When persona changes, invalidate plans and AI responses
    )
    smart_cache.register_invalidation_pattern(
        'user:*:preferences', ['plan:*', 'ai:*']  # When preferences change, invalidate related data
    )
    
    return cache, smart_cache

# Example cached function
async def cached_geocode_address(cache: HybridCache, address: str) -> Dict[str, Any]:
    """Example of cached geocoding function"""
    cache_key = CacheKeyGenerator.geocoding_key(address)
    
    # Try cache first
    cached_result = await cache.get(cache_key)
    if cached_result:
        return cached_result
    
    # Simulate geocoding API call
    result = {
        'address': address,
        'lat': 35.6762,  # Example coordinates for Tokyo
        'lng': 139.6503,
        'formatted_address': f"Formatted: {address}",
        'timestamp': time.time()
    }
    
    # Cache the result
    await cache.set(cache_key, result, ttl=86400)  # 24 hours for geocoding
    
    return result