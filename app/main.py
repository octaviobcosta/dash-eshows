"""
Arquivo de compatibilidade para manter o caminho antigo funcionando.
Redireciona para o novo local do módulo.
"""
from app.core.main import *

# Exportar o server para o gunicorn
__all__ = ['server']