"""Testes Fase 21g.1 — acerto das previsões verificadas."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

from app.services.previsao_verificacao_service import acerto_resumo, backfill_desfechos


def _row(
    *,
    risk: float,
    desfecho: bool | None,
    previsto_em: datetime,
    horizonte_h: int = 24,
    codigo: str = "2611606",
):
    r = MagicMock()
    r.codigo_ibge = codigo
    r.risk_score = risk
    r.desfecho_ocorrido = desfecho
    r.previsto_em = previsto_em
    r.horizonte_h = horizonte_h
    r.desfecho_verificado_em = None
    r.desfecho_fonte = None
    return r


def test_acerto_resumo_calculates_pct():
    now = datetime(2026, 7, 1, 12, 0, tzinfo=timezone.utc)
    rows = [
        _row(risk=0.8, desfecho=True, previsto_em=now - timedelta(days=1)),   # TP
        _row(risk=0.2, desfecho=False, previsto_em=now - timedelta(days=2)),  # TN
        _row(risk=0.9, desfecho=False, previsto_em=now - timedelta(days=3)),  # FP
        _row(risk=0.1, desfecho=True, previsto_em=now - timedelta(days=4)),   # FN
    ]
    # 2 acertos / 4 = 50%

    db = MagicMock()
    verified_q = MagicMock()
    verified_q.filter.return_value.order_by.return_value.limit.return_value.all.return_value = rows
    pending_q = MagicMock()
    pending_q.filter.return_value.count.return_value = 3

    def query_side_effect(model):
        name = getattr(model, "__name__", str(model))
        if "PrevisaoVerificacao" in name:
            # First call path in acerto_resumo after backfill is verified; then pending count
            # Simpler: return object that supports both chains
            q = MagicMock()
            q.filter.return_value = q
            q.order_by.return_value = q
            q.limit.return_value = q
            q.all.return_value = rows
            q.count.return_value = 3
            return q
        return MagicMock()

    db.query.side_effect = query_side_effect

    with patch("app.services.previsao_verificacao_service.backfill_desfechos", return_value={"filled": 0}):
        out = acerto_resumo(db, "2611606", lookback=30, backfill=True)

    assert out["disponivel"] is True
    assert out["n_verificadas"] == 4
    assert out["acerto_pct"] == 50.0
    assert out["tp"] == 1
    assert out["tn"] == 1
    assert out["fp"] == 1
    assert out["fn"] == 1
    assert "Acertamos 50%" in (out["narrativa"] or "")
    assert out["amostra_suficiente"] is False


def test_backfill_fills_expired_horizon():
    now = datetime(2026, 7, 27, 12, 0, tzinfo=timezone.utc)
    row = _row(
        risk=0.6,
        desfecho=None,
        previsto_em=now - timedelta(hours=30),
        horizonte_h=24,
    )

    db = MagicMock()
    q = MagicMock()
    q.filter.return_value = q
    q.order_by.return_value = q
    q.limit.return_value = q
    q.all.return_value = [row]
    db.query.return_value = q

    with patch(
        "app.services.previsao_verificacao_service.utc_now",
        return_value=now,
    ), patch(
        "app.services.previsao_verificacao_service._had_official_event",
        return_value=True,
    ):
        out = backfill_desfechos(db, "2611606")

    assert out["filled"] == 1
    assert row.desfecho_ocorrido is True
    assert row.desfecho_fonte == "evento_oficial"
    db.commit.assert_called_once()


def test_acerto_vazio_sem_verificadas():
    db = MagicMock()
    q = MagicMock()
    q.filter.return_value = q
    q.order_by.return_value = q
    q.limit.return_value = q
    q.all.return_value = []
    q.count.return_value = 2
    db.query.return_value = q

    with patch("app.services.previsao_verificacao_service.backfill_desfechos", return_value={}):
        out = acerto_resumo(db, "2611606", backfill=False)

    assert out["disponivel"] is False
    assert out["acerto_pct"] is None
    assert out["n_pendentes"] == 2
