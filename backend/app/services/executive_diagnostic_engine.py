"""Motor de Diagnóstico Executivo Automático — Etapa 4."""

from __future__ import annotations

import datetime
import logging
from typing import Any

from sqlalchemy.orm import Session

from app.api.analytics import executive_snapshot
from app.api.data_catalog import coverage_for_code
from app.models import (
    AlertaCemaden,
    DiagnosticoExecutivo,
    HistoricoDesastreS2ID,
    Municipio,
    MunicipioFiscal,
    MunicipioIbge,
    MunicipioSeed,
)
from app.services.maturity_engine import compute_maturity
from app.services.action_plan_engine import _severity_from_score, build_action_plan_payload
from app.services.diagnostic_narrative_service import build_narrative_context, generate_executive_narrative
from app.services.report_generator import (
    _capag_interpretation,
    _ensure_capag_fresh,
    build_bairro_ranking,
)

logger = logging.getLogger(__name__)

SCORE_FORMULA = "Score = 45% × IVC + 35% × IRI + 20% × (1 − adaptação)"


def _lacuna_label(item: Any) -> str | None:
    """Normaliza lacuna (string ou dict do catálogo) para texto exibível."""
    if not item:
        return None
    if isinstance(item, str):
        text = item.strip()
        return text or None
    if isinstance(item, dict):
        text = (item.get("nome") or item.get("id") or item.get("label") or "").strip()
        return text or None
    text = str(item).strip()
    return text or None


def _merge_lacunas(*sources: Any) -> list[str]:
    labels: list[str] = []
    seen: set[str] = set()
    for source in sources:
        if not source:
            continue
        for item in source:
            label = _lacuna_label(item)
            if label and label not in seen:
                seen.add(label)
                labels.append(label)
    return sorted(labels)


def _fmt_num(value: float | int | None, suffix: str = "") -> str:
    if value is None:
        return "—"
    if isinstance(value, float):
        text = f"{value:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    else:
        text = f"{value:,}".replace(",", ".")
    return f"{text}{suffix}"


def _fmt_currency(value: float | None) -> str:
    if value is None:
        return "—"
    return f"R$ {_fmt_num(value)}"


def _score_label(score: int) -> str:
    if score >= 66:
        return "prioridade crítica"
    if score >= 33:
        return "prioridade elevada"
    return "prioridade moderada"


def _build_sections(
    db: Session,
    muni: Municipio,
    *,
    ranking: list[dict],
    snapshot: dict,
    ibge: MunicipioIbge | None,
    fiscal: MunicipioFiscal | None,
    capag_meta: dict,
    maturity: dict | None,
    coverage_pct: float,
    coverage_class: str,
    gaps: list,
    seed: MunicipioSeed | None,
) -> dict[str, Any]:
    ten_years = datetime.date.today() - datetime.timedelta(days=365 * 10)
    desastres = (
        db.query(HistoricoDesastreS2ID)
        .filter(
            HistoricoDesastreS2ID.municipio_id == muni.id,
            HistoricoDesastreS2ID.data_ocorrencia >= ten_years,
        )
        .order_by(HistoricoDesastreS2ID.data_ocorrencia.desc())
        .limit(10)
        .all()
    )
    alertas = (
        db.query(AlertaCemaden)
        .filter(AlertaCemaden.municipio_id == muni.id)
        .order_by(AlertaCemaden.data_alerta.desc())
        .limit(5)
        .all()
    )

    top3 = ranking[:3]
    nota_capag = fiscal.nota_capag if fiscal else capag_meta.get("nota")
    pop = ibge.populacao if ibge and ibge.populacao else muni.populacao
    area = float(ibge.area_km2 if ibge and ibge.area_km2 else muni.area_km2 or 0)
    idh = float(ibge.idh) if ibge and ibge.idh else None
    pib_pc = float(ibge.pib_per_capita) if ibge and ibge.pib_per_capita else None

    perfil = {
        "titulo": "Perfil Municipal",
        "municipio": f"{muni.nome}/{muni.uf}",
        "codigo_ibge": muni.codigo_ibge,
        "populacao": pop,
        "area_km2": round(area, 2),
        "densidade_hab_km2": snapshot.get("densidade_demografica"),
        "idh": idh,
        "pib_per_capita": pib_pc,
        "fontes": ["IBGE — Pesquisas 33 e 38", "Malha territorial Sinidu+Clima"],
    }

    fiscal_section = {
        "titulo": "Situação Fiscal",
        "nota_capag": nota_capag,
        "nota_capag_raw": capag_meta.get("nota_capag_raw"),
        "capag_interpretacao": _capag_interpretation(nota_capag),
        "capag_meta": capag_meta,
        "capag_indicadores": capag_meta.get("indicadores") or [],
        "receita_corrente_liquida": float(fiscal.receita_corrente_liquida) if fiscal and fiscal.receita_corrente_liquida else None,
        "despesa_pessoal_pct_rcl": float(fiscal.despesa_pessoal_pct_rcl) if fiscal and fiscal.despesa_pessoal_pct_rcl is not None else None,
        "divida_consolidada": float(fiscal.divida_consolidada) if fiscal and fiscal.divida_consolidada else None,
        "exercicio": fiscal.exercicio if fiscal else None,
        "fontes": ["SICONFI / Tesouro Transparente", "CAPAG — STN"],
    }

    climatica = {
        "titulo": "Situação Climática",
        "score_sinidu": snapshot.get("score_sinidu"),
        "classificacao_risco": _score_label(int(snapshot.get("score_sinidu") or 0)),
        "media_ivc": snapshot.get("media_ivc"),
        "media_iri": snapshot.get("media_iri"),
        "media_adaptacao": snapshot.get("media_adaptacao"),
        "formula": SCORE_FORMULA,
        "alertas_ativos": len(alertas),
        "alertas_recentes": [
            {
                "nivel": a.nivel_alerta,
                "data": a.data_alerta.strftime("%d/%m/%Y %H:%M"),
                "descricao": a.descricao or "—",
            }
            for a in alertas
        ],
        "fontes": ["CEMADEN", "Open-Meteo", "AnalyticalEngine Sinidu+Clima"],
    }

    historico = {
        "titulo": "Histórico de Desastres",
        "total_10_anos": len(desastres),
        "danos_materiais_total": snapshot.get("danos_materiais_total"),
        "eventos": [
            {
                "tipo": d.tipo_desastre,
                "data": d.data_ocorrencia.strftime("%d/%m/%Y"),
                "populacao_afetada": d.populacao_afetada,
                "danos_materiais": float(d.danos_materiais or 0),
            }
            for d in desastres
        ],
        "fontes": ["S2ID — Centro Nacional de Gerenciamento de Riscos e Desastres"],
    }

    vegetal = {
        "titulo": "Cobertura Vegetal",
        "cobertura_vegetal_percent": snapshot.get("cobertura_vegetal_percent"),
        "interpretacao": (
            "Cobertura vegetal abaixo de 20% indica maior pressão sobre drenagem urbana e ilhas de calor."
            if (snapshot.get("cobertura_vegetal_percent") or 0) < 20
            else "Cobertura vegetal compatível com mitigação parcial de eventos extremos."
        ),
        "fontes": ["MapBiomas — Coleção 9", "PostGIS Sinidu+Clima"],
    }

    riscos = {
        "titulo": "Principais Riscos Territoriais",
        "areas_criticas": [
            {
                "bairro": row["bairro"],
                "score_sinidu": row["score_sinidu"],
                "ivc": row["ivc"],
                "iri": row["iri"],
                "classificacao": _score_label(row["score_sinidu"]),
            }
            for row in top3
        ],
        "ranking_completo_top10": ranking[:10],
        "fontes": ["IVC e IRI — AnalyticalEngine", "Malha de bairros"],
    }

    lacunas_list = _merge_lacunas(
        gaps,
        seed.lacunas if seed else None,
        (fonte.get("nome") or fonte.get("id") for fonte in (maturity or {}).get("fontes_faltantes") or []),
    )

    lacunas_section = {
        "titulo": "Lacunas e Maturidade de Dados",
        "maturidade_score": maturity["score"] if maturity else coverage_pct,
        "maturidade_classificacao": maturity["classificacao"] if maturity else coverage_class,
        "lacunas": lacunas_list[:12],
        "recomendacao": (
            "Completar integrações pendentes antes de decisões de investimento de alto impacto."
            if lacunas_list
            else "Base municipal adequada para diagnóstico executivo e plano de ação."
        ),
        "fontes": ["Motor de Maturidade Sinidu+Clima", "Catálogo de Dados"],
    }

    return {
        "perfil_municipal": perfil,
        "situacao_fiscal": fiscal_section,
        "situacao_climatica": climatica,
        "historico_desastres": historico,
        "cobertura_vegetal": vegetal,
        "principais_riscos": riscos,
        "lacunas": lacunas_section,
    }


def _build_narrative(muni: Municipio, sections: dict[str, Any], headline: str) -> str:
    p = sections["perfil_municipal"]
    f = sections["situacao_fiscal"]
    c = sections["situacao_climatica"]
    h = sections["historico_desastres"]
    v = sections["cobertura_vegetal"]
    r = sections["principais_riscos"]
    l = sections["lacunas"]

    lines = [
        f"# Diagnóstico Executivo — {muni.nome}/{muni.uf}",
        "",
        f"**{headline}**",
        "",
        f"*Gerado em {datetime.datetime.now().strftime('%d/%m/%Y %H:%M')} · Sinidu+Clima · IBGE {p['codigo_ibge']}*",
        "",
        "---",
        "",
        "## 1. Perfil Municipal",
        "",
        f"{muni.nome} ({muni.uf}) possui **{_fmt_num(p['populacao'])} habitantes** em **{_fmt_num(p['area_km2'])} km²** "
        f"(densidade {_fmt_num(p['densidade_hab_km2'])} hab/km²).",
    ]
    if p.get("idh"):
        lines.append(f"IDH municipal: **{p['idh']:.3f}** (IBGE).")
    if p.get("pib_per_capita"):
        lines.append(f"PIB per capita: **{_fmt_currency(p['pib_per_capita'])}**.")

    lines.extend([
        "",
        "## 2. Situação Fiscal",
        "",
        f"Nota **CAPAG: {f.get('nota_capag_raw') or f['nota_capag'] or 'não disponível'}**. {f['capag_interpretacao']}",
    ])
    for ind in f.get("capag_indicadores") or []:
        lines.append(
            f"- Indicador {ind.get('numero')} ({ind.get('nome')}): "
            f"valor {ind.get('valor_fmt', '—')} · nota **{ind.get('nota') or '—'}**."
        )
    if f.get("receita_corrente_liquida"):
        lines.append(f"Receita Corrente Líquida: {_fmt_currency(f['receita_corrente_liquida'])}.")
    if f.get("despesa_pessoal_pct_rcl") is not None:
        lines.append(f"Despesa com pessoal: {f['despesa_pessoal_pct_rcl']:.1f}% da RCL.")

    lines.extend([
        "",
        "## 3. Situação Climática",
        "",
        f"Score Sinidu+Clima municipal: **{c['score_sinidu']}** ({c['classificacao_risco']}). "
        f"Fórmula: {c['formula']}.",
        f"IVC médio {c['media_ivc']} · IRI médio {c['media_iri']} · Adaptação média {c['media_adaptacao']}.",
        f"Alertas CEMADEN registrados: **{c['alertas_ativos']}**.",
        "",
        "## 4. Histórico de Desastres (10 anos)",
        "",
    ])
    if h["eventos"]:
        for ev in h["eventos"][:5]:
            lines.append(
                f"- **{ev['tipo']}** ({ev['data']}): "
                f"{_fmt_num(ev['populacao_afetada'] or 0)} pessoas afetadas · "
                f"danos {_fmt_currency(ev['danos_materiais'])}."
            )
        if h.get("danos_materiais_total"):
            lines.append(f"\nTotal estimado de danos materiais: **{_fmt_currency(h['danos_materiais_total'])}**.")
    else:
        lines.append("Nenhum evento S2ID registrado na janela analisada — verificar sincronização da base.")

    lines.extend([
        "",
        "## 5. Cobertura Vegetal",
        "",
        f"Cobertura vegetal municipal: **{v['cobertura_vegetal_percent']}%**. {v['interpretacao']}",
        "",
        "## 6. Principais Riscos Territoriais",
        "",
    ])
    for area in r["areas_criticas"]:
        lines.append(
            f"- **{area['bairro']}** — Score {area['score_sinidu']} ({area['classificacao']}): "
            f"IVC {area['ivc']} · IRI {area['iri']}."
        )

    lines.extend([
        "",
        "## 7. Lacunas e Maturidade de Dados",
        "",
        f"Maturidade municipal: **{l['maturidade_score']:.0f}/100** ({l['maturidade_classificacao']}).",
        l["recomendacao"],
    ])
    if l["lacunas"]:
        lines.append("\nIntegrações ou fontes pendentes:")
        for gap in l["lacunas"][:8]:
            lines.append(f"- {gap}")

    lines.extend([
        "",
        "---",
        "",
        "*Documento gerado automaticamente pelo Sinidu+Clima. Validar dados fiscais (CAPAG/SICONFI) e eventos S2ID antes de uso conclusivo em processos decisórios.*",
    ])
    return "\n".join(lines)


def _build_headline(muni: Municipio, snapshot: dict, top3: list[dict], nota_capag: str | None) -> str:
    score = int(snapshot.get("score_sinidu") or 0)
    areas = ", ".join(row["bairro"] for row in top3[:3]) if top3 else "áreas centrais"
    capag_txt = f" CAPAG {nota_capag}." if nota_capag else ""
    return (
        f"Diagnóstico Sinidu+Clima para {muni.nome}/{muni.uf}: "
        f"Score {score} ({_score_label(score)}); "
        f"prioridades em {areas}.{capag_txt}"
    )


def generate_executive_diagnostic(
    db: Session,
    codigo_ibge: str,
    *,
    origem: str = "manual",
) -> DiagnosticoExecutivo:
    muni = db.query(Municipio).filter(Municipio.codigo_ibge == codigo_ibge).first()
    if not muni:
        raise ValueError(f"Município IBGE {codigo_ibge} não encontrado.")

    ibge = db.query(MunicipioIbge).filter(MunicipioIbge.codigo_ibge == codigo_ibge).first()
    fiscal, capag_meta = _ensure_capag_fresh(db, muni)
    seed = db.query(MunicipioSeed).filter(MunicipioSeed.codigo_ibge == codigo_ibge).first()

    try:
        maturity = compute_maturity(db, codigo_ibge)
    except Exception as exc:
        logger.warning("Maturidade indisponível para diagnóstico %s: %s", codigo_ibge, exc)
        maturity = None

    coverage_pct, _, gaps = coverage_for_code(codigo_ibge, db)
    coverage_class = "Alta" if coverage_pct >= 75 else ("Média" if coverage_pct >= 50 else "Baixa")

    ranking, snapshot = build_bairro_ranking(db, muni)
    nota_capag = fiscal.nota_capag if fiscal else capag_meta.get("nota")

    sections = _build_sections(
        db,
        muni,
        ranking=ranking,
        snapshot=snapshot,
        ibge=ibge,
        fiscal=fiscal,
        capag_meta=capag_meta,
        maturity=maturity,
        coverage_pct=coverage_pct,
        coverage_class=coverage_class,
        gaps=gaps,
        seed=seed,
    )

    headline = _build_headline(muni, snapshot, ranking[:3], nota_capag)
    narrativa = _build_narrative(muni, sections, headline)

    score = int(snapshot.get("score_sinidu") or 0)
    severidade = _severity_from_score(score)
    action_preview = build_action_plan_payload(db, muni, diagnostic_id=None)
    narrative_ctx = build_narrative_context(
        muni.nome,
        muni.uf,
        snapshot=snapshot,
        sections=sections,
        action_plan=action_preview,
        severidade=severidade,
    )
    narrative_result = generate_executive_narrative(narrative_ctx)

    last = (
        db.query(DiagnosticoExecutivo)
        .filter(DiagnosticoExecutivo.codigo_ibge == codigo_ibge)
        .order_by(DiagnosticoExecutivo.versao.desc())
        .first()
    )
    versao = (last.versao + 1) if last else 1

    record = DiagnosticoExecutivo(
        municipio_id=muni.id,
        codigo_ibge=codigo_ibge,
        versao=versao,
        status="concluido",
        headline=headline,
        conteudo={
            **sections,
            "headline": headline,
            "score_sinidu": snapshot.get("score_sinidu"),
            "maturity": maturity,
            "narrativa_ia_paragrafos": narrative_result.get("paragrafos") or [],
        },
        narrativa_md=narrativa,
        narrativa_ia=narrative_result.get("narrativa_ia"),
        narrativa_ia_meta={
            "ai_provider": narrative_result.get("ai_provider"),
            "ai_model": narrative_result.get("ai_model"),
            "disclaimer": narrative_result.get("disclaimer"),
            "paragrafos": narrative_result.get("paragrafos") or [],
        },
        origem=origem,
    )
    db.add(record)
    db.commit()
    db.refresh(record)

    try:
        from app.services.diagnostic_report import generate_diagnostic_pdf

        generate_diagnostic_pdf(record, muni)
    except Exception as exc:
        logger.warning("PDF do diagnóstico falhou para %s: %s", codigo_ibge, exc)

    try:
        from app.services.action_plan_engine import generate_action_plan

        generate_action_plan(db, codigo_ibge, origem="diagnostico", diagnostic_id=record.id)
        logger.info("Plano de ação gerado automaticamente após diagnóstico para %s", codigo_ibge)
    except Exception as exc:
        logger.warning("Plano de ação pós-diagnóstico falhou para %s: %s", codigo_ibge, exc)

    return record


def diagnostic_to_dict(record: DiagnosticoExecutivo) -> dict[str, Any]:
    from app.services.diagnostic_report import diagnostic_download_meta

    pdf_meta = diagnostic_download_meta(record)
    return {
        "id": record.id,
        "municipio_id": record.municipio_id,
        "codigo_ibge": record.codigo_ibge,
        "versao": record.versao,
        "status": record.status,
        "headline": record.headline,
        "conteudo": record.conteudo,
        "narrativa_md": record.narrativa_md,
        "narrativa_ia": record.narrativa_ia,
        "narrativa_ia_meta": record.narrativa_ia_meta or {},
        "origem": record.origem,
        "gerado_em": record.gerado_em.isoformat() if record.gerado_em else None,
        **pdf_meta,
    }
