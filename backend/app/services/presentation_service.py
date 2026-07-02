"""Dados agregados para modo apresentação — Sinidu+Clima Step 4."""

from __future__ import annotations

import datetime
from collections import Counter
from typing import Any

from sqlalchemy.orm import Session

from app.models import Bairro, DiagnosticoExecutivo, Municipio, PlanoAcaoMunicipal
from app.services.action_plan_engine import action_plan_to_dict
from app.services.diagnostic_report import diagnostic_download_meta
from app.services.executive_diagnostic_engine import diagnostic_to_dict
from app.services.map_screenshot_service import map_screenshot_base64
from app.services.report_generator import _capag_interpretation, build_bairro_ranking


def _capag_financing_level(nota: str | None) -> str:
    if nota in {"A", "B"}:
        return "Alta" if nota == "A" else "Média"
    if nota in {"C", "D"}:
        return "Limitada"
    return "Não disponível"


def _risk_label(row: dict) -> str:
    iri = float(row.get("iri") or 0)
    ivc = float(row.get("ivc") or 0)
    if iri >= 0.66:
        return "Inundação"
    if ivc >= 0.66:
        return "Vulnerabilidade climática"
    return "Risco combinado"


def _events_by_year(eventos: list[dict]) -> list[dict]:
    counts: Counter[int] = Counter()
    for ev in eventos:
        data = ev.get("data") or ""
        try:
            year = int(data.split("/")[-1]) if "/" in data else int(str(data)[:4])
            counts[year] += 1
        except (ValueError, IndexError):
            continue
    return [{"ano": year, "eventos": count} for year, count in sorted(counts.items())]


def build_presentation_payload(db: Session, codigo_ibge: str) -> dict[str, Any]:
    muni = db.query(Municipio).filter(Municipio.codigo_ibge == codigo_ibge).first()
    if not muni:
        raise ValueError(f"Município IBGE {codigo_ibge} não encontrado.")

    diagnostic = (
        db.query(DiagnosticoExecutivo)
        .filter(DiagnosticoExecutivo.codigo_ibge == codigo_ibge)
        .order_by(DiagnosticoExecutivo.gerado_em.desc())
        .first()
    )
    if not diagnostic:
        raise ValueError("Nenhum diagnóstico executivo gerado. Execute POST /diagnostic/generate primeiro.")

    action_plan_row = (
        db.query(PlanoAcaoMunicipal)
        .filter(PlanoAcaoMunicipal.codigo_ibge == codigo_ibge)
        .order_by(PlanoAcaoMunicipal.gerado_em.desc())
        .first()
    )
    action_plan = action_plan_to_dict(action_plan_row) if action_plan_row else None

    conteudo = diagnostic.conteudo or {}
    meta = diagnostic.narrativa_ia_meta or {}
    paragrafos = meta.get("paragrafos") or conteudo.get("narrativa_ia_paragrafos") or []
    if not paragrafos and diagnostic.narrativa_ia:
        paragrafos = [p.strip() for p in diagnostic.narrativa_ia.split("\n\n") if p.strip()][:3]

    ranking, snapshot = build_bairro_ranking(db, muni)
    bairro_pop = {
        b.nome: b.pop_censo2022
        for b in db.query(Bairro).filter(Bairro.municipio_id == muni.id).all()
    }

    top5 = []
    for row in ranking[:5]:
        top5.append(
            {
                "bairro": row["bairro"],
                "score": row["score_sinidu"],
                "populacao": bairro_pop.get(row["bairro"]),
                "risco_principal": _risk_label(row),
                "ivc": row.get("ivc"),
                "iri": row.get("iri"),
            }
        )

    fiscal = conteudo.get("situacao_fiscal") or {}
    historico = conteudo.get("historico_desastres") or {}
    eventos = historico.get("eventos") or []
    maior_dano = max((float(ev.get("danos_materiais") or 0) for ev in eventos), default=0.0)
    maior_data = next((ev.get("data") for ev in eventos if float(ev.get("danos_materiais") or 0) == maior_dano), None)

    climatica = conteudo.get("situacao_climatica") or {}
    score = int(snapshot.get("score_sinidu") or conteudo.get("score_sinidu") or 0)
    severidade = action_plan.get("severidade") if action_plan else (
        "Crítica" if score >= 66 else ("Alta" if score >= 33 else "Moderada")
    )

    pdf_meta = diagnostic_download_meta(diagnostic)
    gerado = diagnostic.gerado_em or datetime.datetime.utcnow()

    map_b64 = map_screenshot_base64(db, muni, "vulnerabilidade")

    acoes_curto = (action_plan or {}).get("acoes_curto_prazo") or []
    acoes_medio = (action_plan or {}).get("acoes_medio_prazo") or []
    acoes_longo = (action_plan or {}).get("acoes_longo_prazo") or []

    return {
        "municipio": {
            "nome": muni.nome,
            "uf": muni.uf,
            "codigo_ibge": muni.codigo_ibge,
            "populacao": muni.populacao,
        },
        "diagnostic": diagnostic_to_dict(diagnostic),
        "score": score,
        "severidade": severidade,
        "ivc": snapshot.get("media_ivc"),
        "iri": snapshot.get("media_iri"),
        "data_apresentacao": gerado.strftime("%d/%m/%Y"),
        "narrativa": {
            "texto_completo": diagnostic.narrativa_ia,
            "paragrafos": paragrafos,
            "contexto": paragrafos[0] if len(paragrafos) > 0 else "",
            "prioridades": paragrafos[1] if len(paragrafos) > 1 else "",
            "proximos_passos": paragrafos[2] if len(paragrafos) > 2 else "",
            "disclaimer": meta.get("disclaimer"),
            "ai_provider": meta.get("ai_provider"),
        },
        "mapa": {
            "layer": "vulnerabilidade",
            "png_base64": map_b64,
            "legenda": [
                {"cor": "#ef4444", "label": "Prioridade crítica (≥66)"},
                {"cor": "#f97316", "label": "Prioridade elevada (33–65)"},
                {"cor": "#6366f1", "label": "Prioridade moderada (<33)"},
            ],
        },
        "bairros_prioritarios": top5,
        "historico_desastres": {
            "total_10_anos": historico.get("total_10_anos") or len(eventos),
            "por_ano": _events_by_year(eventos),
            "maior_dano": maior_dano,
            "data_maior_dano": maior_data,
        },
        "saude_fiscal": {
            "capag": fiscal.get("nota_capag_raw") or fiscal.get("nota_capag"),
            "capacidade_financiamento": _capag_financing_level(fiscal.get("nota_capag")),
            "interpretacao": fiscal.get("capag_interpretacao") or _capag_interpretation(fiscal.get("nota_capag")),
            "receita_corrente_liquida": fiscal.get("receita_corrente_liquida"),
            "programas_elegiveis": (action_plan or {}).get("programas_financiamento") or [],
        },
        "plano_acao": {
            "curto_prazo": {"total": len(acoes_curto), "acoes": acoes_curto[:3]},
            "medio_prazo": {"total": len(acoes_medio), "acoes": acoes_medio[:3]},
            "longo_prazo": {"total": len(acoes_longo), "acoes": acoes_longo[:3]},
        },
        "pdf": pdf_meta,
    }
