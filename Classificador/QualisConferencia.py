"""Classificador Qualis de trabalhos publicados em eventos."""

from pathlib import Path
import warnings
from typing import Optional

from QualisLens.qualislens.matcher import match
from QualisLens.qualislens.qualis_db import QualisDB


class QualisConferencia:
    """Integra o QualisLens à interface histórica do ExtratorLattes.

    ``qualis_path`` continua aceitando o TSV legado de 2017-2020 usado nas
    configurações existentes. A base recente distribuída com o QualisLens é
    carregada em conjunto. Também é possível informar explicitamente os dois
    CSVs normalizados.
    """

    def __init__(
        self,
        qualis_path: Optional[str] = None,
        path_2021_2024: Optional[str] = None,
    ) -> None:
        argumentos = {}
        if qualis_path:
            caminho_legado = Path(qualis_path).resolve()
            copia_historica = Path(__file__).resolve().parent / "qualis_conferencias.csv"
            # A configuração PPGI histórica aponta para esta cópia. A fonte
            # canônica é QualisLens/base; não deixe a cópia divergente mudar o
            # produto. Caminhos externos continuam suportados.
            if caminho_legado != copia_historica.resolve():
                argumentos["path_2017"] = str(caminho_legado)
        if path_2021_2024:
            argumentos["path_2025"] = str(Path(path_2021_2024))
        self._db = QualisDB(**argumentos)

    def get_match(
        self,
        venue: str,
        ano: Optional[int] = None,
        sigla: Optional[str] = None,
    ) -> dict:
        """Retorna classificação e diagnóstico completo para um evento.

        Quando ``ano`` é omitido, usa a semântica da interface legada: a base
        2017-2020 configurada. O fluxo PPGI sempre informa o ano real.
        """
        if ano is None:
            warnings.warn(
                "get_match/get_estrato sem ano usa a base legada 2017-2020; "
                "informe ano para uma decisão reprodutível",
                DeprecationWarning,
                stacklevel=2,
            )
            ano = 2020
        resultado = match(
            nome_conferencia=venue,
            ano=ano,
            sigla_conferencia=sigla,
            db=self._db,
        )
        diagnostico = {
            chave: valor
            for chave, valor in resultado.items()
            if not chave.startswith("_")
        }
        # Chaves curtas formam o contrato público. Prefixos qualis_* ficam por
        # compatibilidade com exportadores já existentes.
        diagnostico.update({
            "estrato": diagnostico["qualis_estrato"],
            "evento_oficial": diagnostico["qualis_nome_oficial"],
            "sigla_oficial": diagnostico["qualis_sigla"],
            "quadrienio": diagnostico["qualis_quadrienio"],
            "metodo": diagnostico["qualis_status"],
            "score_primeiro": diagnostico["qualis_score_fuzzy"],
            "margem_segundo": diagnostico["qualis_score_margem"],
            "candidatos": diagnostico["qualis_candidatos"],
            "motivo": diagnostico["qualis_obs"] or diagnostico["qualis_llm_motivo"],
            "necessita_revisao": diagnostico["qualis_requer_revisao"],
        })
        return diagnostico

    def get_estrato(
        self,
        venue: str,
        ano: Optional[int] = None,
        sigla: Optional[str] = None,
    ) -> Optional[str]:
        """Retorna o estrato ou ``None`` quando o caso requer revisão."""
        return self.get_match(venue, ano, sigla).get("qualis_estrato")
