"""Previsão de impacto municipal a partir do risco ML (Fase 21g.2).

Não é chuva: bairros prioritários, população exposta estimada e medidas
filtradas por porte + CAPAG.
"""

from __future__ import annotations

import logging
from typing import Any

from sqlalchemy.orm import Session

from app.models import Bairro, Municipio

logger = logging.getLogger(__name__)

# Bairros com risco ≥ limiar entram na contagem de impacto
IMPACT_RISK_THRESHOLD = 0.45


def _risk_nivel_semaforo(prob: float) -> str:
    from app.services.unified_risk_model import ml_prob_to_nivel

    return ml_prob_to_nivel(prob)


def build_flood_impact(
    db: Session,
    codigo_ibge: str,
    *,
    municipal_prob: float,
    critical_neighborhoods: list[dict[str, Any]],
) -> dict[str, Any]:
    """Monta bloco de impacto para a resposta de `/flood-risk`."""
    code = str(codigo_ibge).zfill(7)[:7]
    muni = db.query(Municipio).filter(Municipio.codigo_ibge == code).first()
    if not muni:
        return {
            "disponivel": False,
            "reason": "municipio_nao_encontrado",
            "protocol": "21g2_impacto",
        }

    pop_muni = int(muni.populacao or 0)
    bairros_db = {
        b.id: b for b in db.query(Bairro).filter(Bairro.municipio_id == muni.id).all()
    }

    afetados: list[dict[str, Any]] = []
    pop_exposta = 0
    for row in critical_neighborhoods:
        prob = float(row.get("risk_probability") or 0)
        if prob < IMPACT_RISK_THRESHOLD:
            continue
        bid = int(row.get("bairro_id") or 0)
        b = bairros_db.get(bid)
        pop_b = 0
        if b is not None and b.pop_censo2022 is not None:
            pop_b = int(b.pop_censo2022)
        elif pop_muni and critical_neighborhoods:
            # Fallback: rateia população municipal pelos bairros críticos
            pop_b = max(0, int(round(pop_muni / max(len(critical_neighborhoods), 1))))
        # Fração exposta ≈ risco do bairro (cap 1.0)
        exposta = int(round(pop_b * min(1.0, max(0.0, prob))))
        pop_exposta += exposta
        afetados.append({
            "bairro_id": bid,
            "bairro_nome": row.get("bairro_nome") or (b.nome if b else "—"),
            "risk_probability": round(prob, 3),
            "populacao_bairro": pop_b or None,
            "populacao_exposta_estimada": exposta,
            "suscetibilidade_local": row.get("suscetibilidade_local"),
        })

    if pop_exposta > pop_muni > 0:
        pop_exposta = pop_muni

    pct_muni = round(100.0 * pop_exposta / pop_muni, 1) if pop_muni else None
    nivel = _risk_nivel_semaforo(float(municipal_prob))
    nomes = [a["bairro_nome"] for a in afetados[:5]]

    perfil = None
    medidas: list[dict[str, Any]] = []
    try:
        from app.services.measures_catalog import recommend_measures
        from app.services.municipal_profile_service import build_municipal_profile

        perfil = build_municipal_profile(db, code)
        medidas = recommend_measures(
            perfil,
            nivel_risco=nivel,
            fatores_principais=["s2id", "impermeabilizacao", "hidrografia", "iri", "exposicao"],
            bairros_alvo=nomes,
            limit=5,
        )
    except Exception as exc:
        logger.info("impacto medidas %s: %s", code, exc)

    capag = (perfil or {}).get("capag") or {}
    porte = (perfil or {}).get("porte")
    narrativa = (
        f"{len(afetados)} bairro(s) prioritário(s); "
        f"população exposta estimada ~{pop_exposta:,}".replace(",", ".")
        + (f" ({pct_muni}% do município)" if pct_muni is not None else "")
        + f". Nível operacional {nivel}."
    )

    return {
        "disponivel": True,
        "protocol": "21g2_impacto",
        "nivel_operacional": nivel,
        "n_bairros_prioritarios": len(afetados),
        "bairros_prioritarios": afetados[:8],
        "populacao_municipio": pop_muni or None,
        "populacao_exposta_estimada": pop_exposta,
        "pct_populacao_exposta": pct_muni,
        "porte": porte,
        "capag_nota": capag.get("nota"),
        "medidas_cabiveis": [
            {
                "id": m.get("id"),
                "titulo": m.get("titulo"),
                "custo": m.get("custo"),
                "horizonte": m.get("horizonte"),
                "prioridade": m.get("prioridade"),
                "orgao": m.get("orgao"),
                "motivo": m.get("motivo"),
            }
            for m in medidas
        ],
        "narrativa": narrativa,
        "nota": (
            "População exposta = Σ (pop. bairro × risco do bairro) nos prioritários. "
            "Medidas filtradas por porte e CAPAG — não são ordem de serviço automática."
        ),
    }
