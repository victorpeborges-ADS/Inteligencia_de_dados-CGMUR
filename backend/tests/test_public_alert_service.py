"""Testes unitários leves — disseminação 17h.3d."""

from app.services.public_alert_service import (
    CANAL_IDS,
    DISPATCH_TIPO,
    _whatsapp_link,
    build_draft_message,
)


class _Muni:
    nome = "Recife"
    uf = "PE"
    codigo_ibge = "2611606"


def test_whatsapp_link_normalizes_br_ddd():
    link = _whatsapp_link("81 98888-7777", "Alerta teste")
    assert link is not None
    assert link.startswith("https://wa.me/5581988887777")
    assert "Alerta" in link


def test_whatsapp_link_rejects_short():
    assert _whatsapp_link("123", "x") is None


def test_draft_message_custom_wins():
    msg = build_draft_message(
        _Muni(),  # type: ignore[arg-type]
        {"nivel_alerta": "VERMELHO", "titulo_recente": "Chuva", "fonte": "cemaden"},
        mensagem_custom="  Mensagem custom  ",
    )
    assert msg == "Mensagem custom"


def test_draft_message_includes_nivel_and_ibge():
    msg = build_draft_message(
        _Muni(),  # type: ignore[arg-type]
        {"nivel_alerta": "LARANJA", "titulo_recente": "Risco elevado", "fonte": "cemaden"},
    )
    assert "LARANJA" in msg
    assert "Recife/PE" in msg
    assert "2611606" in msg


def test_canal_ids_stable():
    assert "checklist_dc" in CANAL_IDS
    assert "sms" in CANAL_IDS
    assert DISPATCH_TIPO == "PUBLIC_ALERT_DISPATCH"
