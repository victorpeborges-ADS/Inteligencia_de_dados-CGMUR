"""Testes do agente contextual otimizado."""

from app.services.contextual_agent_service import _is_simple_question


def test_simple_question_detected():
    assert _is_simple_question("Como usar as camadas socioeconômicas?") is True
    assert _is_simple_question("O que significa o Score Sinidu?") is True


def test_data_question_not_simple():
    assert _is_simple_question("Quais bairros têm maior score IVC?") is False
    assert _is_simple_question("Mostre alertas CEMADEN ativos") is False
