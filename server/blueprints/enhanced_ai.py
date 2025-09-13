"""
Enhanced AI blueprint demonstrating improved implementation methods:
- Advanced caching strategies
- Circuit breaker patterns
- Structured logging and monitoring
- Performance optimization
"""

import asyncio
import time
from flask import Blueprint, request, jsonify, current_app
from werkzeug.exceptions import BadRequest, InternalServerError
import json
import hashlib
from typing import Dict, Any, Optional

# Import our enhanced utilities
from ..utils.caching import HybridCache, CacheKeyGenerator, SmartCache
from ..utils.monitoring import (
    PerformanceMonitor, StructuredLogger, CircuitBreaker, 
    CircuitBreakerConfig, monitor_performance, with_circuit_breaker
)
from ..utils.auth import claims_or_dev  # Assume this exists

# Initialize enhanced components
enhanced_ai_bp = Blueprint('enhanced_ai', __name__)
logger = StructuredLogger(__name__)
performance_monitor = PerformanceMonitor()

# Circuit breakers for external services
gemini_breaker = CircuitBreaker(
    CircuitBreakerConfig(failure_threshold=5, recovery_timeout=60)
)
agent_breaker = CircuitBreaker(
    CircuitBreakerConfig(failure_threshold=3, recovery_timeout=45)
)

# Cache instance (would be initialized with Redis in production)
cache = HybridCache(redis_client=None)  # Mock for demonstration
smart_cache = SmartCache(cache)

class EnhancedAIService:
    """
    Enhanced AI service with improved error handling, caching, and monitoring
    """
    
    def __init__(self, cache: HybridCache, performance_monitor: PerformanceMonitor):
        self.cache = cache
        self.performance_monitor = performance_monitor
        self.logger = StructuredLogger(f"{__name__}.EnhancedAIService")
    
    async def generate_persona_with_caching(
        self, 
        user_id: str, 
        analysis_data: Dict[str, Any],
        force_refresh: bool = False
    ) -> Dict[str, Any]:
        """
        Generate persona with intelligent caching and fallback strategies
        """
        
        with self.logger.context(
            operation="generate_persona",
            user_id=user_id,
            force_refresh=force_refresh
        ) as ctx:
            
            # Generate cache key based on analysis data
            analysis_hash = CacheKeyGenerator.generate_context_hash(analysis_data)
            cache_key = f"persona:user:{user_id}:analysis:{analysis_hash}"
            
            # Try cache first (unless force refresh requested)
            if not force_refresh:
                cached_persona = await self.cache.get(cache_key)
                if cached_persona:
                    self.logger.info("Persona cache hit", cache_key=cache_key)
                    self.performance_monitor.increment_counter(
                        'cache_hits', 
                        {'service': 'persona', 'user_id': user_id}
                    )
                    return cached_persona
            
            # Generate new persona
            self.logger.info("Generating new persona", analysis_hash=analysis_hash)
            start_time = time.time()
            
            try:
                # This would call the actual AI service
                persona_data = await self._call_ai_service_with_fallback(
                    "generate_persona", 
                    analysis_data,
                    ctx.trace_id
                )
                
                # Enrich persona with metadata
                enriched_persona = {
                    **persona_data,
                    'generated_at': time.time(),
                    'analysis_hash': analysis_hash,
                    'trace_id': ctx.trace_id
                }
                
                # Cache the result
                await smart_cache.smart_set(cache_key, enriched_persona, 'persona')
                
                generation_time = time.time() - start_time
                self.performance_monitor.record_duration(
                    'persona_generation', 
                    generation_time,
                    {'user_id': user_id, 'cache_miss': 'true'}
                )
                
                self.logger.info(
                    "Persona generated successfully",
                    generation_time_ms=int(generation_time * 1000),
                    persona_id=enriched_persona.get('id')
                )
                
                return enriched_persona
                
            except Exception as e:
                self.logger.error(
                    "Persona generation failed",
                    error=str(e),
                    error_type=type(e).__name__,
                    analysis_hash=analysis_hash
                )
                raise InternalServerError(f"Failed to generate persona: {str(e)}")
    
    @with_circuit_breaker(agent_breaker)
    async def _call_agent_service(self, payload: Dict[str, Any], trace_id: str) -> Dict[str, Any]:
        """
        Call ADK agent service with circuit breaker protection
        """
        # This would be the actual agent service call
        # For demonstration, we'll simulate the call
        await asyncio.sleep(0.1)  # Simulate network delay
        
        # Simulate occasional failures for circuit breaker demonstration
        import random
        if random.random() < 0.1:  # 10% failure rate for demo
            raise Exception("Agent service temporarily unavailable")
        
        return {
            "agent_response": "Sample agent response",
            "trace_id": trace_id,
            "processing_time_ms": 100
        }
    
    @with_circuit_breaker(gemini_breaker)
    async def _call_gemini_direct(self, prompt: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Call Gemini API directly with circuit breaker protection
        """
        # This would be the actual Gemini API call
        await asyncio.sleep(0.2)  # Simulate API delay
        
        return {
            "gemini_response": f"Generated response for: {prompt[:50]}...",
            "model": "gemini-2.5-pro",
            "context_hash": CacheKeyGenerator.generate_context_hash(context)
        }
    
    async def _call_ai_service_with_fallback(
        self, 
        operation: str, 
        data: Dict[str, Any],
        trace_id: str
    ) -> Dict[str, Any]:
        """
        Call AI service with intelligent fallback strategy
        """
        
        # Try ADK agent service first
        try:
            self.logger.info("Attempting ADK agent service call", operation=operation)
            result = await self._call_agent_service(data, trace_id)
            self.performance_monitor.increment_counter(
                'ai_service_calls', 
                {'service': 'agent', 'operation': operation, 'status': 'success'}
            )
            return result
            
        except Exception as agent_error:
            self.logger.warning(
                "ADK agent service failed, falling back to Gemini direct",
                error=str(agent_error),
                operation=operation
            )
            
            # Fallback to Gemini direct
            try:
                prompt = self._generate_prompt_for_operation(operation, data)
                result = await self._call_gemini_direct(prompt, data)
                
                self.performance_monitor.increment_counter(
                    'ai_service_calls', 
                    {'service': 'gemini_direct', 'operation': operation, 'status': 'fallback_success'}
                )
                return result
                
            except Exception as gemini_error:
                self.logger.error(
                    "Both AI services failed",
                    agent_error=str(agent_error),
                    gemini_error=str(gemini_error),
                    operation=operation
                )
                
                self.performance_monitor.increment_counter(
                    'ai_service_calls', 
                    {'service': 'all', 'operation': operation, 'status': 'failed'}
                )
                
                # Return cached fallback if available
                fallback_result = await self._get_fallback_response(operation, data)
                if fallback_result:
                    self.logger.info("Using cached fallback response", operation=operation)
                    return fallback_result
                
                raise Exception(f"All AI services unavailable for operation: {operation}")
    
    def _generate_prompt_for_operation(self, operation: str, data: Dict[str, Any]) -> str:
        """Generate appropriate prompt for Gemini direct calls"""
        prompt_templates = {
            "generate_persona": f"Generate a travel persona based on this analysis: {json.dumps(data, indent=2)}",
            "create_travel_plan": f"Create a travel plan based on these preferences: {json.dumps(data, indent=2)}",
            "default": f"Process this request for {operation}: {json.dumps(data, indent=2)}"
        }
        return prompt_templates.get(operation, prompt_templates["default"])
    
    async def _get_fallback_response(self, operation: str, data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Get cached fallback response for critical failures"""
        fallback_key = f"fallback:{operation}:{CacheKeyGenerator.generate_context_hash(data)}"
        return await self.cache.get(fallback_key)

# Initialize enhanced service
enhanced_ai_service = EnhancedAIService(cache, performance_monitor)

@enhanced_ai_bp.route('/api/enhanced/persona', methods=['POST'])
@monitor_performance(performance_monitor, 'persona_generation')
async def enhanced_create_persona():
    """
    Enhanced persona creation endpoint with caching and monitoring
    """
    
    try:
        # Extract request data
        claims = claims_or_dev()
        user_id = claims.get('sub', 'anonymous')
        analysis_data = request.get_json()
        
        if not analysis_data:
            raise BadRequest("Analysis data is required")
        
        # Check for force refresh parameter
        force_refresh = request.args.get('force_refresh', 'false').lower() == 'true'
        
        with logger.context(
            operation="enhanced_create_persona",
            user_id=user_id,
            trace_id=request.headers.get('X-Trace-ID', f"trace-{int(time.time())}")
        ):
            
            # Generate persona using enhanced service
            persona = await enhanced_ai_service.generate_persona_with_caching(
                user_id=user_id,
                analysis_data=analysis_data,
                force_refresh=force_refresh
            )
            
            logger.info("Persona creation completed successfully")
            
            return jsonify({
                'success': True,
                'persona': persona,
                'cached': persona.get('generated_at', 0) < time.time() - 60,  # Check if older than 1 minute
                'trace_id': persona.get('trace_id')
            })
    
    except BadRequest as e:
        logger.warning("Invalid request for persona creation", error=str(e))
        return jsonify({'success': False, 'error': str(e)}), 400
    
    except Exception as e:
        logger.error("Unexpected error in persona creation", error=str(e))
        return jsonify({'success': False, 'error': 'Internal server error'}), 500

@enhanced_ai_bp.route('/api/enhanced/chat', methods=['POST'])
@monitor_performance(performance_monitor, 'enhanced_chat')
async def enhanced_agent_chat():
    """
    Enhanced agent chat with intelligent caching and fallback
    """
    
    try:
        claims = claims_or_dev()
        user_id = claims.get('sub', 'anonymous')
        data = request.get_json()
        
        message = data.get('message', '').strip()
        session_id = data.get('session_id', 'default')
        
        if not message:
            raise BadRequest("Message is required")
        
        if len(message) > 2000:
            raise BadRequest("Message too long (max 2000 characters)")
        
        with logger.context(
            operation="enhanced_agent_chat",
            user_id=user_id,
            session_id=session_id,
            message_length=len(message)
        ) as ctx:
            
            # Generate cache key for chat response
            context_data = {
                'user_id': user_id,
                'session_id': session_id,
                'message': message
            }
            context_hash = CacheKeyGenerator.generate_context_hash(context_data)
            cache_key = f"chat:user:{user_id}:session:{session_id}:ctx:{context_hash}"
            
            # Check cache for similar recent conversations
            cached_response = await cache.get(cache_key)
            if cached_response:
                logger.info("Chat response cache hit")
                performance_monitor.increment_counter(
                    'cache_hits', 
                    {'service': 'chat', 'user_id': user_id}
                )
                return jsonify({
                    'success': True,
                    'reply': cached_response['reply'],
                    'cached': True,
                    'trace_id': ctx.trace_id
                })
            
            # Process with AI service
            chat_data = {
                'message': message,
                'session_id': session_id,
                'user_context': context_data
            }
            
            ai_response = await enhanced_ai_service._call_ai_service_with_fallback(
                "agent_chat",
                chat_data,
                ctx.trace_id
            )
            
            # Process and cache response
            processed_response = {
                'reply': ai_response.get('agent_response', ai_response.get('gemini_response', 'No response generated')),
                'generated_at': time.time(),
                'trace_id': ctx.trace_id,
                'service_used': 'agent' if 'agent_response' in ai_response else 'gemini'
            }
            
            # Cache with shorter TTL for chat responses
            await cache.set(cache_key, processed_response, ttl=180)  # 3 minutes
            
            logger.info("Chat response generated successfully")
            
            return jsonify({
                'success': True,
                'reply': processed_response['reply'],
                'cached': False,
                'service_used': processed_response['service_used'],
                'trace_id': ctx.trace_id
            })
    
    except BadRequest as e:
        logger.warning("Invalid chat request", error=str(e))
        return jsonify({'success': False, 'error': str(e)}), 400
    
    except Exception as e:
        logger.error("Unexpected error in chat processing", error=str(e))
        return jsonify({'success': False, 'error': 'Internal server error'}), 500

@enhanced_ai_bp.route('/api/enhanced/metrics', methods=['GET'])
def get_enhanced_metrics():
    """
    Get performance metrics for the enhanced AI service
    """
    
    try:
        # Get performance metrics
        metrics = performance_monitor.get_metrics_summary()
        
        # Get cache statistics
        cache_stats = cache.get_cache_stats()
        
        # Get circuit breaker states
        circuit_breaker_stats = {
            'gemini_breaker': {
                'state': gemini_breaker.state.value,
                'failure_count': gemini_breaker.failure_count,
                'last_failure_time': gemini_breaker.last_failure_time
            },
            'agent_breaker': {
                'state': agent_breaker.state.value,
                'failure_count': agent_breaker.failure_count,
                'last_failure_time': agent_breaker.last_failure_time
            }
        }
        
        return jsonify({
            'success': True,
            'timestamp': time.time(),
            'performance_metrics': metrics,
            'cache_statistics': cache_stats,
            'circuit_breakers': circuit_breaker_stats
        })
    
    except Exception as e:
        logger.error("Failed to get enhanced metrics", error=str(e))
        return jsonify({'success': False, 'error': 'Failed to retrieve metrics'}), 500

@enhanced_ai_bp.route('/api/enhanced/health', methods=['GET'])
def enhanced_health_check():
    """
    Enhanced health check with detailed service status
    """
    
    try:
        health_status = {
            'status': 'healthy',
            'timestamp': time.time(),
            'services': {
                'cache': {
                    'status': 'healthy' if cache else 'unavailable',
                    'details': cache.get_cache_stats() if cache else None
                },
                'gemini_circuit_breaker': {
                    'status': 'healthy' if gemini_breaker.state.value == 'closed' else gemini_breaker.state.value,
                    'failure_count': gemini_breaker.failure_count
                },
                'agent_circuit_breaker': {
                    'status': 'healthy' if agent_breaker.state.value == 'closed' else agent_breaker.state.value,
                    'failure_count': agent_breaker.failure_count
                }
            }
        }
        
        # Determine overall health
        unhealthy_services = [
            name for name, service in health_status['services'].items()
            if service['status'] not in ['healthy', 'closed']
        ]
        
        if unhealthy_services:
            health_status['status'] = 'degraded'
            health_status['unhealthy_services'] = unhealthy_services
        
        status_code = 200 if health_status['status'] in ['healthy', 'degraded'] else 503
        
        return jsonify(health_status), status_code
    
    except Exception as e:
        logger.error("Health check failed", error=str(e))
        return jsonify({
            'status': 'error',
            'error': str(e),
            'timestamp': time.time()
        }), 503