"""Verificação previsão → desfecho e taxa de acerto (Fase 21g.1).

Preenche `desfecho_ocorrido` após o horizonte e publica
“Acertamos Y% das últimas Z previsões” para o gestor.
"""

from __future__ import annotations

import datetime as dt
import logging
from typing import Any

from sqlalchemy.orm import Session

from app.models import EventoAlagamentoObservado, HistoricoDesastreS2ID, Municipio, PrevisaoVerificacao
from app.timeutil import utc_now
from ml.constants import FLOOD_EVENT_TYPES
from ml.features import ML_LABEL_QUALITIES

logger = logging.getLogger(__name__)

# Score ≥ limiar = “previu risco elevado”
DEFAULT_RISK_THRESHOLD = 0.50
DEFAULT_LOOKBACK = 30  # últimas Z previsões verificadas


def _is_flood_type(tipo: str) -> bool:
    t = tipo or ""
    return t in FLOOD_EVENT_TYPES or "Inunda" in t or "Alag" in t or "Enxurr" in t


def _had_official_event(
    db: Session,
    codigo_ibge: str,
    window_start: dt.datetime,
    window_end: dt.datetime,
) -> bool:
    """True se houve evento oficial de alagamento na janela da previsão."""
    code = str(codigo_ibge).zfill(7)[:7]

    obs = (
        db.query(EventoAlagamentoObservado.id)
        .filter(
            EventoAlagamentoObservado.codigo_ibge == code,
            EventoAlagamentoObservado.data_quality.in_(tuple(ML_LABEL_QUALITIES)),
            EventoAlagamentoObservado.inicio_em >= window_start,
            EventoAlagamentoObservado.inicio_em <= window_end,
        )
        .first()
    )
    if obs:
        return True

    muni = db.query(Municipio).filter(Municipio.codigo_ibge == code).first()
    if not muni:
        return False

    start_d = window_start.date() if hasattr(window_start, "date") else window_start
    end_d = window_end.date() if hasattr(window_end, "date") else window_end
    rows = (
        db.query(HistoricoDesastreS2ID)
        .filter(
            HistoricoDesastreS2ID.municipio_id == muni.id,
            HistoricoDesastreS2ID.data_quality.in_(tuple(ML_LABEL_QUALITIES)),
            HistoricoDesastreS2ID.data_ocorrencia >= start_d,
            HistoricoDesastreS2ID.data_ocorrencia <= end_d,
        )
        .all()
    )
    return any(_is_flood_type(r.tipo_desastre) for r in rows)


def backfill_desfechos(
    db: Session,
    codigo_ibge: str | None = None,
    *,
    limit: int = 500,
) -> dict[str, Any]:
    """Preenche desfechos de previsões cujo horizonte já expirou."""
    now = utc_now()
    q = db.query(PrevisaoVerificacao).filter(PrevisaoVerificacao.desfecho_ocorrido.is_(None))
    if codigo_ibge:
        q = q.filter(PrevisaoVerificacao.codigo_ibge == str(codigo_ibge).zfill(7)[:7])
    pending = q.order_by(PrevisaoVerificacao.previsto_em.asc()).limit(limit).all()

    filled = 0
    skipped_horizon = 0
    for row in pending:
        horizonte = int(row.horizonte_h or 24)
        deadline = row.previsto_em + dt.timedelta(hours=horizonte)
        if now < deadline:
            skipped_horizon += 1
            continue
        occurred = _had_official_event(db, row.codigo_ibge, row.previsto_em, deadline)
        row.desfecho_ocorrido = bool(occurred)
        row.desfecho_verificado_em = now
        row.desfecho_fonte = "evento_oficial" if occurred else "sem_evento_oficial"
        filled += 1

    if filled:
        db.commit()
    return {
        "filled": filled,
        "pending_horizon": skipped_horizon,
        "scanned": len(pending),
    }


def acerto_resumo(
    db: Session,
    codigo_ibge: str,
    *,
    lookback: int = DEFAULT_LOOKBACK,
    risk_threshold: float = DEFAULT_RISK_THRESHOLD,
    backfill: bool = True,
) -> dict[str, Any]:
    """Calcula Y% de acerto nas últimas Z previsões já verificadas (21g.1)."""
    code = str(codigo_ibge).zfill(7)[:7]
    if backfill:
        try:
            backfill_desfechos(db, code)
        except Exception as exc:
            logger.info("backfill desfechos %s: %s", code, exc)

    z = max(1, min(int(lookback), 200))
    thr = float(risk_threshold)

    verified = (
        db.query(PrevisaoVerificacao)
        .filter(
            PrevisaoVerificacao.codigo_ibge == code,
            PrevisaoVerificacao.desfecho_ocorrido.isnot(None),
        )
        .order_by(PrevisaoVerificacao.previsto_em.desc())
        .limit(z)
        .all()
    )
    pending = (
        db.query(PrevisaoVerificacao)
        .filter(
            PrevisaoVerificacao.codigo_ibge == code,
            PrevisaoVerificacao.desfecho_ocorrido.is_(None),
        )
        .count()
    )

    n = len(verified)
    if n == 0:
        return {
            "disponivel": False,
            "codigo_ibge": code,
            "n_verificadas": 0,
            "n_pendentes": pending,
            "lookback": z,
            "acerto_pct": None,
            "narrativa": (
                "Ainda sem previsões verificadas neste município. "
                "O sistema acumula previsão × desfecho a cada sync do Monitor."
            ),
            "limiar_risco": thr,
            "protocol": "21g1_acerto_previsoes",
        }

    hits = 0
    tp = fp = tn = fn = 0
    for row in verified:
        pred_pos = float(row.risk_score or 0) >= thr
        actual = bool(row.desfecho_ocorrido)
        if pred_pos == actual:
            hits += 1
        if pred_pos and actual:
            tp += 1
        elif pred_pos and not actual:
            fp += 1
        elif (not pred_pos) and (not actual):
            tn += 1
        else:
            fn += 1

    acerto_pct = round(100.0 * hits / n, 1)
    suficientes = n >= 5
    narrativa = (
        f"Acertamos {acerto_pct:.0f}% das últimas {n} previsões verificadas "
        f"(limiar de risco {thr:.0%})."
    )
    if not suficientes:
        narrativa += " Amostra ainda pequena — interprete com cautela."

    return {
        "disponivel": True,
        "codigo_ibge": code,
        "n_verificadas": n,
        "n_pendentes": pending,
        "lookback": z,
        "acerto_pct": acerto_pct,
        "acertos": hits,
        "tp": tp,
        "fp": fp,
        "tn": tn,
        "fn": fn,
        "limiar_risco": thr,
        "amostra_suficiente": suficientes,
        "narrativa": narrativa,
        "protocol": "21g1_acerto_previsoes",
        "nota": (
            "Acerto = (previu risco elevado) coincide com (houve evento oficial no horizonte). "
            "Não é AUC; é a métrica que o gestor vê no dia a dia."
        ),
    }
