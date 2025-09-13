"""
Advanced monitoring and observability utilities for the Izatabi travel planning application.
Implements structured logging, metrics collection, and health monitoring.
"""

import time
import uuid
import asyncio
import logging
from typing import Dict, Any, Optional, Callable
from functools import wraps
from dataclasses import dataclass, asdict
from datetime import datetime
from contextlib import contextmanager
from enum import Enum
import json

# Circuit Breaker Implementation
class CircuitBreakerState(Enum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"

@dataclass
class CircuitBreakerConfig:
    failure_threshold: int = 5
    recovery_timeout: int = 60
    expected_exception: type = Exception

class CircuitBreaker:
    """
    Circuit breaker pattern implementation for external service calls
    """
    
    def __init__(self, config: CircuitBreakerConfig):
        self.config = config
        self.failure_count = 0
        self.last_failure_time: Optional[float] = None
        self.state = CircuitBreakerState.CLOSED
        self.logger = logging.getLogger(f"{__name__}.CircuitBreaker")
    
    def _should_attempt_reset(self) -> bool:
        """Check if we should attempt to reset the circuit breaker"""
        return (
            self.state == CircuitBreakerState.OPEN and
            self.last_failure_time and
            time.time() - self.last_failure_time >= self.config.recovery_timeout
        )
    
    def _record_success(self):
        """Record successful operation"""
        self.failure_count = 0
        self.last_failure_time = None
        if self.state != CircuitBreakerState.CLOSED:
            self.logger.info("Circuit breaker reset to CLOSED state")
            self.state = CircuitBreakerState.CLOSED
    
    def _record_failure(self):
        """Record failed operation"""
        self.failure_count += 1
        self.last_failure_time = time.time()
        
        if self.failure_count >= self.config.failure_threshold:
            self.state = CircuitBreakerState.OPEN
            self.logger.warning(
                f"Circuit breaker opened after {self.failure_count} failures"
            )
    
    async def call(self, func: Callable, *args, **kwargs) -> Any:
        """Execute function with circuit breaker protection"""
        
        # Check if we should attempt reset
        if self._should_attempt_reset():
            self.state = CircuitBreakerState.HALF_OPEN
            self.logger.info("Circuit breaker entering HALF_OPEN state")
        
        # Fast fail if circuit is open
        if self.state == CircuitBreakerState.OPEN:
            raise Exception(
                f"Circuit breaker is OPEN. Service unavailable for "
                f"{self.config.recovery_timeout - (time.time() - self.last_failure_time):.1f} more seconds"
            )
        
        try:
            if asyncio.iscoroutinefunction(func):
                result = await func(*args, **kwargs)
            else:
                result = func(*args, **kwargs)
            
            self._record_success()
            return result
            
        except self.config.expected_exception as e:
            self._record_failure()
            raise e

# Structured Logging
@dataclass
class LogContext:
    """Structured logging context"""
    trace_id: str
    user_id: Optional[str] = None
    session_id: Optional[str] = None
    operation: Optional[str] = None
    service: Optional[str] = None
    extra_data: Optional[Dict[str, Any]] = None

class StructuredLogger:
    """
    Structured logger with automatic context management
    """
    
    def __init__(self, name: str):
        self.logger = logging.getLogger(name)
        self.context_stack = []
    
    @contextmanager
    def context(self, **context_data):
        """Context manager for scoped logging context"""
        context = LogContext(
            trace_id=context_data.get('trace_id', str(uuid.uuid4())),
            **{k: v for k, v in context_data.items() if k != 'trace_id'}
        )
        self.context_stack.append(context)
        try:
            yield context
        finally:
            self.context_stack.pop()
    
    def _get_current_context(self) -> Dict[str, Any]:
        """Get current logging context"""
        if not self.context_stack:
            return {}
        
        context = self.context_stack[-1]
        return {k: v for k, v in asdict(context).items() if v is not None}
    
    def _log(self, level: str, message: str, **extra_data):
        """Internal logging method with context"""
        log_data = {
            'timestamp': datetime.utcnow().isoformat(),
            'level': level.upper(),
            'message': message,
            **self._get_current_context(),
            **extra_data
        }
        
        # Log as JSON for structured logging systems
        self.logger.log(
            getattr(logging, level.upper()),
            json.dumps(log_data, default=str)
        )
    
    def info(self, message: str, **extra_data):
        self._log('info', message, **extra_data)
    
    def warning(self, message: str, **extra_data):
        self._log('warning', message, **extra_data)
    
    def error(self, message: str, **extra_data):
        self._log('error', message, **extra_data)
    
    def debug(self, message: str, **extra_data):
        self._log('debug', message, **extra_data)

# Performance Monitoring
class PerformanceMonitor:
    """
    Performance monitoring with automatic metrics collection
    """
    
    def __init__(self):
        self.metrics = {
            'request_count': {},
            'request_duration': {},
            'error_count': {},
            'cache_hit_rate': {},
        }
        self.logger = StructuredLogger(__name__)
    
    def increment_counter(self, metric: str, labels: Dict[str, str] = None):
        """Increment a counter metric"""
        labels = labels or {}
        key = f"{metric}:{':'.join(f'{k}={v}' for k, v in labels.items())}"
        
        if key not in self.metrics['request_count']:
            self.metrics['request_count'][key] = 0
        self.metrics['request_count'][key] += 1
    
    def record_duration(self, metric: str, duration: float, labels: Dict[str, str] = None):
        """Record duration metric"""
        labels = labels or {}
        key = f"{metric}:{':'.join(f'{k}={v}' for k, v in labels.items())}"
        
        if key not in self.metrics['request_duration']:
            self.metrics['request_duration'][key] = []
        self.metrics['request_duration'][key].append(duration)
    
    def get_metrics_summary(self) -> Dict[str, Any]:
        """Get summary of collected metrics"""
        summary = {}
        
        # Counter metrics
        for key, count in self.metrics['request_count'].items():
            summary[f"counter_{key}"] = count
        
        # Duration metrics (with percentiles)
        for key, durations in self.metrics['request_duration'].items():
            if durations:
                sorted_durations = sorted(durations)
                n = len(sorted_durations)
                summary[f"duration_{key}"] = {
                    'count': n,
                    'avg': sum(durations) / n,
                    'min': min(durations),
                    'max': max(durations),
                    'p50': sorted_durations[int(0.5 * n)],
                    'p95': sorted_durations[int(0.95 * n)],
                    'p99': sorted_durations[int(0.99 * n)] if n > 100 else sorted_durations[-1]
                }
        
        return summary

# Service Health Monitor
@dataclass
class ServiceHealthCheck:
    name: str
    check_function: Callable
    timeout: float = 5.0
    critical: bool = True

class ServiceHealthMonitor:
    """
    Monitor health of external dependencies
    """
    
    def __init__(self):
        self.health_checks: Dict[str, ServiceHealthCheck] = {}
        self.last_check_results: Dict[str, Dict[str, Any]] = {}
        self.logger = StructuredLogger(__name__)
    
    def register_health_check(self, check: ServiceHealthCheck):
        """Register a health check"""
        self.health_checks[check.name] = check
    
    async def check_service_health(self, service_name: str) -> Dict[str, Any]:
        """Check health of a specific service"""
        if service_name not in self.health_checks:
            return {'status': 'unknown', 'error': 'Health check not registered'}
        
        check = self.health_checks[service_name]
        start_time = time.time()
        
        try:
            if asyncio.iscoroutinefunction(check.check_function):
                result = await asyncio.wait_for(check.check_function(), timeout=check.timeout)
            else:
                result = check.check_function()
            
            duration = time.time() - start_time
            health_result = {
                'status': 'healthy',
                'response_time_ms': int(duration * 1000),
                'timestamp': datetime.utcnow().isoformat(),
                'details': result if isinstance(result, dict) else {'response': result}
            }
            
            self.logger.info(
                f"Health check passed for {service_name}",
                service=service_name,
                duration_ms=int(duration * 1000)
            )
            
        except asyncio.TimeoutError:
            health_result = {
                'status': 'timeout',
                'response_time_ms': int(check.timeout * 1000),
                'timestamp': datetime.utcnow().isoformat(),
                'error': f'Health check timed out after {check.timeout}s'
            }
            
            self.logger.warning(
                f"Health check timeout for {service_name}",
                service=service_name,
                timeout_seconds=check.timeout
            )
            
        except Exception as e:
            duration = time.time() - start_time
            health_result = {
                'status': 'unhealthy',
                'response_time_ms': int(duration * 1000),
                'timestamp': datetime.utcnow().isoformat(),
                'error': str(e),
                'error_type': type(e).__name__
            }
            
            self.logger.error(
                f"Health check failed for {service_name}",
                service=service_name,
                error=str(e),
                error_type=type(e).__name__
            )
        
        self.last_check_results[service_name] = health_result
        return health_result
    
    async def check_all_services(self) -> Dict[str, Dict[str, Any]]:
        """Check health of all registered services"""
        tasks = [
            self.check_service_health(service_name)
            for service_name in self.health_checks.keys()
        ]
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        return {
            service_name: result if not isinstance(result, Exception) else {
                'status': 'error',
                'error': str(result),
                'timestamp': datetime.utcnow().isoformat()
            }
            for service_name, result in zip(self.health_checks.keys(), results)
        }
    
    def get_overall_health(self) -> Dict[str, Any]:
        """Get overall system health summary"""
        if not self.last_check_results:
            return {'status': 'unknown', 'message': 'No health checks performed yet'}
        
        critical_services = [
            name for name, check in self.health_checks.items() if check.critical
        ]
        
        critical_unhealthy = [
            name for name in critical_services
            if self.last_check_results.get(name, {}).get('status') != 'healthy'
        ]
        
        if critical_unhealthy:
            return {
                'status': 'unhealthy',
                'message': f'Critical services unhealthy: {", ".join(critical_unhealthy)}',
                'unhealthy_services': critical_unhealthy
            }
        
        all_unhealthy = [
            name for name, result in self.last_check_results.items()
            if result.get('status') != 'healthy'
        ]
        
        if all_unhealthy:
            return {
                'status': 'degraded',
                'message': f'Some services unhealthy: {", ".join(all_unhealthy)}',
                'unhealthy_services': all_unhealthy
            }
        
        return {
            'status': 'healthy',
            'message': 'All services are healthy'
        }

# Decorators for automatic monitoring
def monitor_performance(monitor: PerformanceMonitor, operation_name: str):
    """Decorator to automatically monitor function performance"""
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            start_time = time.time()
            labels = {'operation': operation_name, 'function': func.__name__}
            
            try:
                result = await func(*args, **kwargs)
                labels['status'] = 'success'
                return result
            except Exception as e:
                labels['status'] = 'error'
                labels['error_type'] = type(e).__name__
                monitor.increment_counter('error_count', labels)
                raise
            finally:
                duration = time.time() - start_time
                monitor.record_duration('request_duration', duration, labels)
                monitor.increment_counter('request_count', labels)
        
        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            start_time = time.time()
            labels = {'operation': operation_name, 'function': func.__name__}
            
            try:
                result = func(*args, **kwargs)
                labels['status'] = 'success'
                return result
            except Exception as e:
                labels['status'] = 'error'
                labels['error_type'] = type(e).__name__
                monitor.increment_counter('error_count', labels)
                raise
            finally:
                duration = time.time() - start_time
                monitor.record_duration('request_duration', duration, labels)
                monitor.increment_counter('request_count', labels)
        
        return async_wrapper if asyncio.iscoroutinefunction(func) else sync_wrapper
    
    return decorator

def with_circuit_breaker(breaker: CircuitBreaker):
    """Decorator to add circuit breaker protection to a function"""
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, **kwargs):
            return await breaker.call(func, *args, **kwargs)
        return wrapper
    return decorator

# Example health check functions
async def check_gemini_api_health() -> Dict[str, Any]:
    """Example health check for Gemini API"""
    # This would make a lightweight API call to verify connectivity
    return {'api_endpoint': 'https://generativelanguage.googleapis.com', 'status': 'reachable'}

async def check_firestore_health() -> Dict[str, Any]:
    """Example health check for Firestore"""
    # This would perform a lightweight read operation
    return {'database': 'firestore', 'connectivity': 'ok'}

async def check_agent_service_health() -> Dict[str, Any]:
    """Example health check for ADK Agent Service"""
    # This would ping the agent service health endpoint
    return {'service': 'agent-service', 'endpoint': 'http://agent-service:8080/health'}

# Setup function for monitoring infrastructure
def setup_monitoring() -> tuple[PerformanceMonitor, ServiceHealthMonitor, StructuredLogger]:
    """Setup monitoring infrastructure"""
    
    # Initialize monitoring components
    performance_monitor = PerformanceMonitor()
    health_monitor = ServiceHealthMonitor()
    logger = StructuredLogger('izatabi.monitoring')
    
    # Register health checks
    health_monitor.register_health_check(
        ServiceHealthCheck('gemini_api', check_gemini_api_health, timeout=10.0, critical=True)
    )
    health_monitor.register_health_check(
        ServiceHealthCheck('firestore', check_firestore_health, timeout=5.0, critical=True)
    )
    health_monitor.register_health_check(
        ServiceHealthCheck('agent_service', check_agent_service_health, timeout=15.0, critical=False)
    )
    
    logger.info("Monitoring infrastructure initialized")
    
    return performance_monitor, health_monitor, logger