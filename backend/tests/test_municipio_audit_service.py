"""Testes do serviço de auditoria municipal."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

from app.services.municipio_audit_service import _confiabilidade_geral


def test_confiabilidade_critica_sem_malha():
    malha = {"flag_malha": "MALHA_AUSENTE"}
    socio = {"flag_socio": "SOCIOEC_AUSENTE"}
    seg = {"flag_seg": "SEG_AUSENTE"}
    score = {"flag_score": "SCORE_BAIXA_CONFIANCA", "campos_reais_pct": 10}
    assert _confiabilidade_geral(malha, socio, seg, score) == "CRITICA"


def test_confiabilidade_alta():
    malha = {"flag_malha": "MALHA_OK"}
    socio = {"flag_socio": "SOCIOEC_REAL"}
    seg = {"flag_seg": "SEG_REAL"}
    score = {"flag_score": "SCORE_OK", "campos_reais_pct": 60}
    assert _confiabilidade_geral(malha, socio, seg, score) == "ALTA"
