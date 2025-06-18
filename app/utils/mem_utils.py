import logging
import os

try:
    import resource
except ImportError:
    resource = None
    import psutil

logger = logging.getLogger(__name__)

def log_memory_usage(etapa: str) -> None:
    """Registra no logger o uso de memória atual em MB."""
    if resource is not None:
        mem_kb = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        mem_mb = mem_kb / 1024
    else:
        proc = psutil.Process(os.getpid())
        mem_mb = proc.memory_info().rss / (1024 * 1024)
    logger.info("[mem] %s: %.1f MB", etapa, mem_mb)

from functools import wraps

def log_mem(prefix: str = None):
    """Decorador para logar uso de memória antes e depois da função."""
    def decorator(func):
        etapa = prefix or func.__name__
        @wraps(func)
        def wrapper(*args, **kwargs):
            log_memory_usage(f"{etapa}_inicio")
            result = func(*args, **kwargs)
            log_memory_usage(f"{etapa}_fim")
            return result
        return wrapper
    return decorator
