"""Acompanhamento de execução do plano de ação (17h.3e).

Persiste status por ação dentro de `conteudo.acompanhamento` do PlanoAcaoMunicipal
e registra reavaliações de risco (snapshot do painel semáforo).
"""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.models import PlanoAcaoMunicipal
from app.services.action_plan_engine import action_plan_to_dict
from app.timeutil import utc_now_iso_z

STATUS_OK = {"planejada", "em_andamento", "executada", "cancelada"}


def _utcnow() -> str:
    return utc_now_iso_z()


def _ensure_acompanhamento(conteudo: dict[str, Any]) -> dict[str, Any]:
    ac = conteudo.get("acompanhamento")
    if not isinstance(ac, dict):
        ac = {}
    ac.setdefault("acoes", {})
    ac.setdefault("reavaliacoes", [])
    conteudo["acompanhamento"] = ac
    return ac


def _all_action_ids(conteudo: dict[str, Any]) -> set[str]:
    ids: set[str] = set()
    for key in ("acoes_curto_prazo", "acoes_medio_prazo", "acoes_longo_prazo"):
        for item in conteudo.get(key) or []:
            if isinstance(item, dict) and item.get("id"):
                ids.add(str(item["id"]))
    return ids


def patch_action_status(
    db: Session,
    record: PlanoAcaoMunicipal,
    action_id: str,
    *,
    status: str,
    nota: str | None = None,
    responsavel: str | None = None,
) -> dict[str, Any]:
    st = (status or "").strip().lower()
    if st not in STATUS_OK:
        raise ValueError(f"Status inválido. Use: {', '.join(sorted(STATUS_OK))}")

    conteudo = dict(record.conteudo or {})
    known = _all_action_ids(conteudo)
    if known and action_id not in known:
        raise ValueError(f"Ação '{action_id}' não encontrada neste plano.")

    ac = _ensure_acompanhamento(conteudo)
    prev = dict(ac["acoes"].get(action_id) or {})
    prev.update(
        {
            "action_id": action_id,
            "status": st,
            "atualizado_em": _utcnow(),
        }
    )
    if nota is not None:
        prev["nota"] = nota
    if responsavel is not None:
        prev["responsavel"] = responsavel
    ac["acoes"][action_id] = prev
    record.conteudo = conteudo
    db.commit()
    db.refresh(record)
    return action_plan_to_dict(record)


def get_acompanhamento_summary(record: PlanoAcaoMunicipal) -> dict[str, Any]:
    conteudo = record.conteudo or {}
    ac = conteudo.get("acompanhamento") or {}
    acoes_map = ac.get("acoes") or {}
    all_ids = _all_action_ids(conteudo)
    counts = {s: 0 for s in STATUS_OK}
    for aid in all_ids:
        st = (acoes_map.get(aid) or {}).get("status") or "planejada"
        counts[st] = counts.get(st, 0) + 1
    for aid, row in acoes_map.items():
        if aid not in all_ids:
            st = (row or {}).get("status") or "planejada"
            counts[st] = counts.get(st, 0) + 1
    total = sum(counts.values()) or len(all_ids)
    executadas = counts.get("executada", 0)
    return {
        "plano_id": record.id,
        "codigo_ibge": record.codigo_ibge,
        "versao": record.versao,
        "total_acoes": total,
        "contagem": counts,
        "pct_executada": round(100 * executadas / total, 1) if total else 0,
        "acoes": acoes_map,
        "reavaliacoes": ac.get("reavaliacoes") or [],
    }


def reavaliar_risco(
    db: Session,
    record: PlanoAcaoMunicipal,
    *,
    nota: str | None = None,
) -> dict[str, Any]:
    from app.services.risk_traffic_light_service import build_risk_panel

    panel = build_risk_panel(db, record.codigo_ibge, top_bairros=5)
    conteudo = dict(record.conteudo or {})
    ac = _ensure_acompanhamento(conteudo)
    prev_score = conteudo.get("score_sinidu")
    reavs = list(ac.get("reavaliacoes") or [])
    if reavs:
        prev_score = reavs[-1].get("score_depois", prev_score)

    snap = panel.get("snapshot") or {}
    score_depois = snap.get("score_sinidu")
    if score_depois is None:
        comp = (panel.get("componentes") or {}).get("score") or {}
        score_depois = comp.get("valor")

    try:
        score_depois_f = float(score_depois) if score_depois is not None else None
    except (TypeError, ValueError):
        score_depois_f = None
    try:
        prev_f = float(prev_score) if prev_score is not None else None
    except (TypeError, ValueError):
        prev_f = None

    entry = {
        "em": _utcnow(),
        "score_antes": prev_f,
        "score_depois": score_depois_f,
        "delta_score": (
            round(score_depois_f - prev_f, 2)
            if score_depois_f is not None and prev_f is not None
            else None
        ),
        "nivel": panel.get("status"),
        "nota": nota,
        "acao_sugerida": panel.get("acao_sugerida"),
    }
    reavs.append(entry)
    ac["reavaliacoes"] = reavs[-20:]
    record.conteudo = conteudo
    db.commit()
    db.refresh(record)
    return {
        "plano": action_plan_to_dict(record),
        "reavaliacao": entry,
        "risk_panel_resumo": {
            "status": panel.get("status"),
            "status_label": panel.get("status_label"),
            "score_sinidu": score_depois_f,
            "modo_baixa_maturidade": panel.get("modo_baixa_maturidade"),
        },
    }
