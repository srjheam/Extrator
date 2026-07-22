"""Deduplicação auditável de publicações do PPGI."""
from .core import POLITICA_V1, ResultadoDeduplicacao, deduplicar_publicacoes, id_ocorrencia

__all__ = ["POLITICA_V1", "ResultadoDeduplicacao", "deduplicar_publicacoes", "id_ocorrencia"]
