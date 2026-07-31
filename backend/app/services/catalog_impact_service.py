"""Análise de impacto de lacunas e maturidade enriquecida — Step 5."""

from __future__ import annotations

from app.timeutil import utc_now
import logging
from typing import Any

from sqlalchemy.orm import Session

from app.services.catalog_coverage import BASE_CATALOG, coverage_for_code
from app.models import Municipio, MunicipioSeed
from app.services.catalog_source_registry import FONTE_REGISTRY, RADAR_AXES, STATUS_SCORE
from app.services.catalog_sync_service import get_source_sync_meta

logger = logging.getLogger(__name__)

MONTH_LABELS = ("jan", "fev", "mar", "abr", "mai", "jun", "jul", "ago", "set", "out", "nov", "dez")


def _fonte_nome(fonte_id: str) -> str:
    for item in BASE_CATALOG:
        if item["id"] == fonte_id:
            return item["nome"]
    return fonte_id


def _deterministic_explanation(fonte_id: str, meta: dict[str, Any], status: str) -> str:
    nome = _fonte_nome(fonte_id)
    campos = ", ".join(meta.get("campos_score") or [])
    pts = meta.get("impacto_score_pts", 3)
    diff = meta.get("dificuldade", "Técnica")
    req = meta.get("requisito", "")
    desc = meta.get("descricao_curta", nome)

    prazo = "6 meses" if diff == "Convênio" else ("2 meses" if diff == "Técnica" else "4 meses")
    status_note = {
        "Ausente": f"Sem esta fonte, os campos {campos} dependem de estimativas.",
        "Estimado": f"A fonte está parcialmente integrada; {campos} usam proxies.",
        "Em integracao": f"Integração em curso — {campos} ainda não refletem dados oficiais.",
        "Integrado": f"Fonte operacional para {campos}.",
    }.get(status, "")

    return (
        f"{nome} — {desc} {status_note} "
        f"Integrar plenamente esta fonte pode aumentar a precisão do Score em ±{pts} pontos "
        f"e a confiabilidade em {meta.get('impacto_confiabilidade', 3)} pontos. "
        f"Dificuldade: {diff}. Requer: {req} (prazo estimado: {prazo})."
    )


def analyze_fonte_impact(
    db: Session,
    codigo_ibge: str,
    fonte_id: str,
    *,
    use_ai: bool = True,
) -> dict[str, Any]:
    meta = FONTE_REGISTRY.get(fonte_id)
    if not meta:
        raise ValueError(f"Fonte desconhecida: {fonte_id}")

    _, bases, _ = coverage_for_code(codigo_ibge, db)
    base = next((b for b in bases if b["id"] == fonte_id), None)
    status = base["status"] if base else "Ausente"

    payload = {
        "fonte_id": fonte_id,
        "fonte_nome": _fonte_nome(fonte_id),
        "status_atual": status,
        "campos_score": meta["campos_score"],
        "impacto_confiabilidade": meta["impacto_confiabilidade"],
        "impacto_score_estimado": meta["impacto_score_pts"],
        "dificuldade": meta["dificuldade"],
        "requisito": meta["requisito"],
        "explicacao_ia": _deterministic_explanation(fonte_id, meta, status),
        "ai_provider": "deterministic",
    }

    if use_ai:
        try:
            from rag.providers.registry import resolve_chat_provider_with_fallback

            provider = resolve_chat_provider_with_fallback(None)
            if provider.is_available():
                muni = db.query(Municipio).filter(Municipio.codigo_ibge == codigo_ibge).first()
                prompt = f"""Explique em linguagem simples para gestores municipais o impacto da lacuna de dados abaixo.
Município: {muni.nome if muni else codigo_ibge}
Fonte: {payload['fonte_nome']} (status: {status})
Campos do Score afetados: {', '.join(meta['campos_score'])}
Impacto estimado no Score: ±{meta['impacto_score_pts']} pontos
Dificuldade de integração: {meta['dificuldade']}
Requisito: {meta['requisito']}

Escreva 1 parágrafo claro, sem markdown, mencionando riscos de subestimar vulnerabilidades quando aplicável."""
                text = provider.chat(
                    [
                        {"role": "system", "content": "Você explica lacunas de dados para prefeitos e secretários."},
                        {"role": "user", "content": prompt},
                    ],
                    model=provider.info().default_model,
                    temperature=0.2,
                )
                if text and text.strip():
                    payload["explicacao_ia"] = text.strip()
                    payload["ai_provider"] = provider.id
        except Exception as exc:
            logger.warning("Impact analysis IA failed for %s: %s", fonte_id, exc)

    return payload


def rank_lacunas(bases: list[dict[str, Any]]) -> list[dict[str, Any]]:
    gaps = [b for b in bases if b["status"] in ("Ausente", "Em integracao", "Estimado")]
    ranked = []
    for item in gaps:
        meta = FONTE_REGISTRY.get(item["id"], {})
        ranked.append({
            "id": item["id"],
            "nome": item["nome"],
            "status": item["status"],
            "impacto_estimado": meta.get("impacto_score_pts", 2),
            "impacto_label": f"±{meta.get('impacto_score_pts', 2)} pts Score",
            "impacto_confiabilidade": meta.get("impacto_confiabilidade", 2),
            "dificuldade": meta.get("dificuldade", "Técnica"),
            "requisito": meta.get("requisito"),
        })
    ranked.sort(key=lambda x: (x["impacto_estimado"], x["impacto_confiabilidade"]), reverse=True)
    for i, row in enumerate(ranked, start=1):
        row["rank"] = i
    return ranked


def build_maturity_detail(db: Session, codigo_ibge: str) -> dict[str, Any]:
    maturidade, bases, gaps = coverage_for_code(codigo_ibge, db)
    base_by_id = {b["id"]: b for b in bases}

    radar = []
    for axis, fonte_ids in RADAR_AXES.items():
        scores = [STATUS_SCORE.get(base_by_id[f]["status"], 0) for f in fonte_ids if f in base_by_id]
        pct = round((sum(scores) / len(scores)) * 100) if scores else 0
        radar.append({"eixo": axis, "valor": pct})

    seed = db.query(MunicipioSeed).filter(MunicipioSeed.codigo_ibge == codigo_ibge).first()
    prev = float(seed.maturity_score) if seed and seed.maturity_score else max(maturidade - 4, 0)
    if prev > maturidade:
        prev = max(maturidade - 4, 0)

    now = utc_now()
    mes_atual = MONTH_LABELS[now.month - 1]
    mes_anterior = MONTH_LABELS[(now.month - 2) % 12]
    delta = maturidade - round(prev)

    ranked = rank_lacunas(bases)
    proj_gain = sum(r["impacto_estimado"] for r in ranked[:2]) if ranked else 0
    projecao = min(100, maturidade + proj_gain)

    explicacao = (
        f"Maturidade de {maturidade}% indica que {len([b for b in bases if b['status'] == 'Integrado'])} de "
        f"{len(bases)} fontes estão plenamente integradas. "
        f"Cada ponto percentual aumenta a confiabilidade do diagnóstico executivo e reduz incerteza nas simulações pluviais."
    )

    try:
        from rag.providers.registry import resolve_chat_provider_with_fallback

        provider = resolve_chat_provider_with_fallback(None)
        if provider.is_available():
            muni = db.query(Municipio).filter(Municipio.codigo_ibge == codigo_ibge).first()
            prompt = (
                f"Em 2 frases para gestores: o que significa maturidade informacional de {maturidade}% "
                f"para {muni.nome if muni else codigo_ibge}? Lacunas principais: "
                f"{', '.join(g['nome'] for g in ranked[:3])}."
            )
            text = provider.chat(
                [{"role": "user", "content": prompt}],
                model=provider.info().default_model,
                temperature=0.2,
            )
            if text and text.strip():
                explicacao = text.strip()
    except Exception:
        pass

    return {
        "maturidade_percentual": maturidade,
        "radar": radar,
        "timeline": {
            "anterior": round(prev),
            "atual": maturidade,
            "delta": delta,
            "label": f"Maturidade em {mes_anterior}/{now.year}: {round(prev)}% → {mes_atual}/{now.year}: {maturidade}% ({'+' if delta >= 0 else ''}{delta}%)",
        },
        "projecao": {
            "percentual": projecao,
            "fontes_alvo": [r["nome"] for r in ranked[:2]],
            "label": f"Se integrar {' + '.join(r['nome'] for r in ranked[:2])}: estimado {projecao}%"
            if ranked
            else f"Maturidade estável em {maturidade}%",
        },
        "explicacao_ia": explicacao,
        "lacunas_ranking": ranked,
    }


def enrich_bases(db: Session, codigo_ibge: str, bases: list[dict[str, Any]]) -> list[dict[str, Any]]:
    enriched = []
    for base in bases:
        meta = FONTE_REGISTRY.get(base["id"], {})
        sync = get_source_sync_meta(db, codigo_ibge, base["id"])
        impact_conf = meta.get("impacto_confiabilidade", 0)
        row = {
            **base,
            "ultima_sync": sync.get("ultima_sync"),
            "registros": sync.get("registros", 0),
            "requisito": meta.get("requisito") or sync.get("requisito"),
            "impacto_confiabilidade": impact_conf if base["status"] == "Estimado" else None,
            "impacto_confiabilidade_label": f"-{impact_conf} pts confiabilidade" if base["status"] == "Estimado" else None,
            "integravel_etl": meta.get("integravel_etl", False),
            "dificuldade": meta.get("dificuldade"),
            "impacto_score_pts": meta.get("impacto_score_pts"),
        }
        if base["id"] == "gemeo_digital_3d":
            from app.services.building_catalog_service import catalog_meta_gemeo_digital

            meta3d = catalog_meta_gemeo_digital(db, codigo_ibge)
            row["modelo_3d"] = {
                "lod": meta3d.get("lod"),
                "maturidade_3d_pct": meta3d.get("maturidade_3d_pct"),
                "por_fonte_altura": meta3d.get("por_fonte_altura"),
                "por_qualidade": meta3d.get("por_qualidade"),
                "fonte_altura_predominante": meta3d.get("fonte_altura_predominante"),
                "especificacao": meta3d.get("especificacao"),
                "tileset_url": (meta3d.get("tiles_3d") or {}).get("tileset_url"),
                "cityjson_url": (meta3d.get("citymodel") or {}).get("cityjson_url"),
                "citygml_url": (meta3d.get("citymodel") or {}).get("citygml_url"),
            }
        enriched.append(row)
    return enriched
