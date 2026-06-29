from app.assistant.siconfi_ia_bridge import (
    classify_fiscal_topic,
    detect_fiscal_intent,
    build_siconfi_ia_url,
    _topic_answer,
)


def test_detect_fiscal_intent_meio_ambiente():
    assert detect_fiscal_intent("Quanto Recife gasta com meio ambiente?") is True


def test_detect_fiscal_intent_territorial_false():
    assert detect_fiscal_intent("Quais bairros possuem maior risco?") is False


def test_classify_topic_meio_ambiente():
    assert classify_fiscal_topic("gastos com meio ambiente") == "meio_ambiente"


def test_build_siconfi_ia_url():
    url = build_siconfi_ia_url("Recife", "PE", "Quanto gasta com meio ambiente?")
    assert "siconfi-ia.tesourotransparente.gov.br" in url
    assert "Recife" in url


def test_topic_answer_meio_ambiente():
    text = _topic_answer("meio_ambiente", {
        "nome": "Recife",
        "exercicio": 2024,
        "exec_meio_ambiente": 1500000.0,
        "receita_corrente_liquida": 10000000.0,
    })
    assert "meio ambiente" in text.lower()
    assert "Recife" in text
