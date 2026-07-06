"""Motor de Plano de Ação Municipal — Etapa 9."""

from __future__ import annotations

import logging
from typing import Any

from sqlalchemy.orm import Session

from app.models import DiagnosticoExecutivo, Municipio, PlanoAcaoMunicipal
from app.services.federal_financing_catalog import suggest_programs
from app.services.maturity_engine import compute_maturity
from app.services.mitigation_planner import MitigationPlanner
from app.services.report_generator import _ensure_capag_fresh, build_bairro_ranking

logger = logging.getLogger(__name__)

HORIZON_SHORT = "Curto prazo"
HORIZON_MED = "Médio prazo"
HORIZON_LONG = "Longo prazo"

COST_LOW = "Baixo"
COST_MED = "Médio"
COST_HIGH = "Alto"


def _severity_from_score(score: int) -> str:
    if score >= 66:
        return "Crítica"
    if score >= 33:
        return "Alta"
    if score >= 20:
        return "Moderada"
    return "Baixa"


def _normalize_horizon(text: str) -> str:
    t = (text or "").lower()
    if any(k in t for k in ("imediata", "imediato", "0-6", "resposta imediata")):
        return HORIZON_SHORT
    if any(k in t for k in ("curto", "0-12", "6 meses", "adaptação")):
        return HORIZON_SHORT
    if any(k in t for k in ("médio", "medio", "12-24", "planejamento")):
        return HORIZON_MED
    if any(k in t for k in ("estrutural", "longo", "permanente", "carteira")):
        return HORIZON_LONG
    return HORIZON_MED


def _action(
    *,
    action_id: str,
    titulo: str,
    descricao: str,
    horizonte: str,
    custo: str,
    prioridade: str,
    justificativa: str,
    fonte: str,
    orgao: str,
    bairros_alvo: list[str] | None = None,
) -> dict[str, Any]:
    return {
        "id": action_id,
        "titulo": titulo,
        "descricao": descricao,
        "horizonte": horizonte,
        "custo": custo,
        "prioridade": prioridade,
        "justificativa": justificativa,
        "fonte": fonte,
        "orgao": orgao,
        "bairros_alvo": bairros_alvo or [],
        "casos_referencia": [],
    }


def _actions_from_mitigation(db: Session, muni: Municipio, top_bairros: list[str]) -> list[dict]:
    items: list[dict] = []
    try:
        plan = MitigationPlanner.build_rainfall_plan(db, muni, 120.0)
        for idx, raw in enumerate(plan.get("acoes_tecnicas_padrao") or []):
            data = raw.model_dump() if hasattr(raw, "model_dump") else (raw.dict() if hasattr(raw, "dict") else raw)
            horizonte = _normalize_horizon(data.get("horizonte", ""))
            custo = COST_MED if horizonte == HORIZON_MED else (COST_HIGH if horizonte == HORIZON_LONG else COST_LOW)
            items.append(
                _action(
                    action_id=f"mit_{idx}",
                    titulo=(data.get("acao") or "Ação técnica")[:80],
                    descricao=data.get("acao", ""),
                    horizonte=horizonte,
                    custo=custo,
                    prioridade="Alta" if horizonte == HORIZON_SHORT else "Média",
                    justificativa=data.get("justificativa", ""),
                    fonte="MitigationPlanner / cenário chuva 120 mm",
                    orgao="Secretaria de Obras / Defesa Civil",
                    bairros_alvo=top_bairros[:5],
                )
            )
    except Exception as exc:
        logger.warning("Plano de mitigação base não gerado para %s: %s", muni.codigo_ibge, exc)
    return items


def _territorial_actions(
    muni: Municipio,
    snapshot: dict,
    top_bairros: list[str],
    veg_pct: float,
    s2id_count: int,
    nota_capag: str | None,
) -> list[dict]:
    score = int(snapshot.get("score_sinidu") or 0)
    severity = _severity_from_score(score)
    bairros_txt = ", ".join(top_bairros[:3]) if top_bairros else "áreas centrais"
    actions: list[dict] = []

    actions.append(
        _action(
            action_id="mon_cemaden",
            titulo="Monitoramento integrado CEMADEN + Defesa Civil",
            descricao="Articular alertas hidrológicos ativos com protocolo municipal de resposta e comunicação às áreas expostas.",
            horizonte=HORIZON_SHORT,
            custo=COST_LOW,
            prioridade="Alta" if severity in {"Alta", "Crítica"} else "Média",
            justificativa=f"Score Sinidu+Clima {score} indica prioridade {severity.lower()}.",
            fonte="CEMADEN + Sinidu+Clima",
            orgao="Defesa Civil / Secretaria de Meio Ambiente",
            bairros_alvo=top_bairros[:5],
        )
    )

    if top_bairros:
        actions.append(
            _action(
                action_id="microdrenagem",
                titulo="Desobstrução e microdrenagem nos bairros críticos",
                descricao=f"Priorizar limpeza de bocas de lobo, galerias pluviais e pontos de alagamento recorrente em {bairros_txt}.",
                horizonte=HORIZON_SHORT,
                custo=COST_MED,
                prioridade="Alta",
                justificativa=f"IRI médio {snapshot.get('media_iri')} e bairros prioritários identificados.",
                fonte="AnalyticalEngine / MapBiomas",
                orgao="Secretaria de Obras / Saneamento",
                bairros_alvo=top_bairros[:5],
            )
        )

    if veg_pct < 25:
        actions.append(
            _action(
                action_id="revegetacao",
                titulo="Arborização e revegetação urbana",
                descricao=f"Cobertura vegetal municipal em {veg_pct:.1f}% — implantar corredores verdes e arborização de via pública.",
                horizonte=HORIZON_MED,
                custo=COST_MED,
                prioridade="Média",
                justificativa="Baixa cobertura vegetal aumenta escoamento superficial e ilhas de calor.",
                fonte="MapBiomas / Sinidu+Clima",
                orgao="Secretaria de Meio Ambiente / Urbanismo",
            )
        )

    if s2id_count > 0:
        actions.append(
            _action(
                action_id="contingencia_s2id",
                titulo="Atualizar plano de contingência com histórico S2ID",
                descricao=f"Incorporar {s2id_count} evento(s) registrado(s) na matriz de risco e rotas de evacuação.",
                horizonte=HORIZON_SHORT,
                custo=COST_LOW,
                prioridade="Alta",
                justificativa="Histórico S2ID comprova recorrência de eventos no território.",
                fonte="S2ID / CENAD",
                orgao="Defesa Civil",
            )
        )

    actions.append(
        _action(
            action_id="nbs_drenagem",
            titulo="Soluções baseadas na natureza e retenção pluvial",
            descricao="Carteira de jardins de chuva, valas de infiltração e reservatórios de detenção nas bacias prioritárias.",
            horizonte=HORIZON_LONG,
            custo=COST_HIGH,
            prioridade="Alta" if severity in {"Alta", "Crítica"} else "Média",
            justificativa="Medida estrutural para redução permanente de pico de vazão urbana.",
            fonte="Sinidu+Clima / boas práticas MCID",
            orgao="Secretaria de Obras / Planejamento Urbano",
            bairros_alvo=top_bairros[:5],
        )
    )

    if nota_capag in {"C", "D"}:
        actions.append(
            _action(
                action_id="priorizar_nao_reembolsavel",
                titulo="Priorizar ações de baixo custo e fontes não reembolsáveis",
                descricao="CAPAG restritiva — focar capacitação, prevenção e apoio técnico federal antes de operações de crédito.",
                horizonte=HORIZON_SHORT,
                custo=COST_LOW,
                prioridade="Alta",
                justificativa=f"Nota CAPAG {nota_capag} limita garantia da União.",
                fonte="CAPAG / Tesouro Nacional",
                orgao="Secretaria de Finanças / Controle Interno",
            )
        )

    actions.append(
        _action(
            action_id="carteira_obras",
            titulo="Carteira priorizada de obras de drenagem e adaptação climática",
            descricao="Consolidar estudos, projetos executivos e cronograma plurianual alinhado ao Plano Diretor.",
            horizonte=HORIZON_LONG,
            custo=COST_HIGH,
            prioridade="Alta" if severity == "Crítica" else "Média",
            justificativa="Integração entre diagnóstico territorial, fiscal e planejamento urbano.",
            fonte="Plano Diretor / Sinidu+Clima",
            orgao="Secretaria de Obras / Planejamento",
            bairros_alvo=top_bairros[:5],
        )
    )

    return actions


def _group_by_horizon(actions: list[dict]) -> dict[str, list[dict]]:
    grouped = {HORIZON_SHORT: [], HORIZON_MED: [], HORIZON_LONG: []}
    seen: set[str] = set()
    for item in actions:
        key = item.get("titulo", "")
        if key in seen:
            continue
        seen.add(key)
        h = item.get("horizonte", HORIZON_MED)
        if h not in grouped:
            grouped[HORIZON_MED].append(item)
        else:
            grouped[h].append(item)
    return grouped


def build_action_plan_payload(
    db: Session,
    muni: Municipio,
    *,
    diagnostic_id: int | None = None,
) -> dict[str, Any]:
    ranking, snapshot = build_bairro_ranking(db, muni)
    fiscal, capag_meta = _ensure_capag_fresh(db, muni)
    nota_capag = fiscal.nota_capag if fiscal else capag_meta.get("nota")

    top_bairros = [row["bairro"] for row in ranking[:5]]
    score = int(snapshot.get("score_sinidu") or 0)
    severity = _severity_from_score(score)
    veg_pct = float(snapshot.get("cobertura_vegetal_percent") or 0)
    s2id_count = int(snapshot.get("historico_desastres_count") or 0)
    media_ivc = float(snapshot.get("media_ivc") or 0)

    territorial = _territorial_actions(muni, snapshot, top_bairros, veg_pct, s2id_count, nota_capag)
    mitigation = _actions_from_mitigation(db, muni, top_bairros)
    all_actions = territorial + mitigation
    grouped = _group_by_horizon(all_actions)

    try:
        from app.services.casos_sucesso_service import enrich_all_actions

        grouped[HORIZON_SHORT] = enrich_all_actions(db, grouped[HORIZON_SHORT], muni)
        grouped[HORIZON_MED] = enrich_all_actions(db, grouped[HORIZON_MED], muni)
        grouped[HORIZON_LONG] = enrich_all_actions(db, grouped[HORIZON_LONG], muni)
    except Exception as exc:
        logger.warning("Enriquecimento com casos de sucesso falhou: %s", exc)

    programas = suggest_programs(severidade=severity, nota_capag=nota_capag, media_ivc=media_ivc)

    try:
        maturity = compute_maturity(db, muni.codigo_ibge)
    except Exception:
        maturity = None

    lacunas: list[str] = []
    if not nota_capag:
        lacunas.append("CAPAG não disponível — revisar elegibilidade a crédito.")
    if s2id_count == 0:
        lacunas.append("Sem eventos S2ID locais — experiências próprias limitadas.")
    if maturity and maturity.get("fontes_faltantes"):
        lacunas.extend(f["nome"] for f in maturity["fontes_faltantes"][:3])

    capacidade = {
        "nota_capag": nota_capag,
        "nota_capag_raw": capag_meta.get("nota_capag_raw"),
        "media_ivc": media_ivc,
        "score_sinidu": score,
        "receita_corrente_liquida": float(fiscal.receita_corrente_liquida) if fiscal and fiscal.receita_corrente_liquida else None,
        "alertas": [],
    }
    if nota_capag in {"C", "D"}:
        capacidade["alertas"].append("CAPAG restritiva — priorizar fontes não reembolsáveis.")

    headline = (
        f"Plano de ação Sinidu+Clima para {muni.nome}/{muni.uf}: "
        f"severidade {severity}, Score {score}, {len(all_actions)} ações propostas."
    )

    fontes = [
        {"id": "ibge", "label": "IBGE / Perfil municipal", "tipo": "OFICIAL"},
        {"id": "sinidu", "label": "Score e ranking Sinidu+Clima", "tipo": "DERIVADO"},
        {"id": "capag", "label": "CAPAG / SICONFI", "tipo": "OFICIAL"},
        {"id": "s2id", "label": "Histórico S2ID", "tipo": "OFICIAL"},
        {"id": "mapbiomas", "label": "Cobertura vegetal MapBiomas", "tipo": "OFICIAL"},
    ]
    if diagnostic_id:
        fontes.append({"id": "diagnostico", "label": "Diagnóstico Executivo vinculado", "tipo": "DERIVADO"})

    return {
        "municipio": {
            "codigo_ibge": muni.codigo_ibge,
            "nome": muni.nome,
            "uf": muni.uf,
            "populacao": muni.populacao,
            "area_km2": float(muni.area_km2),
        },
        "severidade": severity,
        "score_sinidu": score,
        "headline": headline,
        "diagnostic_id": diagnostic_id,
        "acoes_curto_prazo": grouped[HORIZON_SHORT],
        "acoes_medio_prazo": grouped[HORIZON_MED],
        "acoes_longo_prazo": grouped[HORIZON_LONG],
        "total_acoes": len(all_actions),
        "programas_financiamento": programas,
        "capacidade_fiscal": capacidade,
        "maturidade": maturity,
        "ranking_bairros": ranking[:8],
        "lacunas": lacunas,
        "fontes_consultadas": fontes,
    }


def generate_action_plan(
    db: Session,
    codigo_ibge: str,
    *,
    origem: str = "manual",
    diagnostic_id: int | None = None,
) -> PlanoAcaoMunicipal:
    muni = db.query(Municipio).filter(Municipio.codigo_ibge == codigo_ibge).first()
    if not muni:
        raise ValueError(f"Município IBGE {codigo_ibge} não encontrado.")

    if diagnostic_id is None:
        latest_diag = (
            db.query(DiagnosticoExecutivo)
            .filter(DiagnosticoExecutivo.codigo_ibge == codigo_ibge)
            .order_by(DiagnosticoExecutivo.gerado_em.desc())
            .first()
        )
        if latest_diag:
            diagnostic_id = latest_diag.id

    payload = build_action_plan_payload(db, muni, diagnostic_id=diagnostic_id)

    last = (
        db.query(PlanoAcaoMunicipal)
        .filter(PlanoAcaoMunicipal.codigo_ibge == codigo_ibge)
        .order_by(PlanoAcaoMunicipal.versao.desc())
        .first()
    )
    versao = (last.versao + 1) if last else 1

    record = PlanoAcaoMunicipal(
        municipio_id=muni.id,
        codigo_ibge=codigo_ibge,
        versao=versao,
        diagnostic_id=diagnostic_id,
        status="concluido",
        severidade=payload["severidade"],
        headline=payload["headline"],
        conteudo=payload,
        origem=origem,
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    return record


def action_plan_to_dict(record: PlanoAcaoMunicipal) -> dict[str, Any]:
    content = record.conteudo or {}
    return {
        "id": record.id,
        "municipio_id": record.municipio_id,
        "codigo_ibge": record.codigo_ibge,
        "versao": record.versao,
        "diagnostic_id": record.diagnostic_id,
        "status": record.status,
        "severidade": record.severidade,
        "headline": record.headline,
        "origem": record.origem,
        "gerado_em": record.gerado_em.isoformat() if record.gerado_em else None,
        **content,
    }
