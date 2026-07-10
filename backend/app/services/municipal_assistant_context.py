"""Contexto municipal para o Assistente Sinidu+Clima — Etapa 8."""

from __future__ import annotations

import json
from typing import Any

from sqlalchemy.orm import Session

from app.api.analytics import executive_snapshot
from app.data_connectors.capag_collector import collect_capag_municipality
from app.models import DiagnosticoExecutivo, Municipio, MunicipioFiscal, MunicipioIbge, RelatorioMunicipal
from app.services.georedus_reference_service import georedus_municipio_url, georedus_summary_for_context
from app.services.maturity_engine import compute_maturity
from app.services.report_generator import build_bairro_ranking


CAPAG_FONTES = "https://www.tesourotransparente.gov.br/ckan/dataset/capag-municipios"
IBGE_FONTES = "https://servicodados.ibge.gov.br/"
S2ID_FONTES = "https://www.gov.br/mdr/pt-br/assuntos/protecao-e-defesa-civil"


def _source(source_id: str, label: str, snippet: str, url: str = "", tipo: str = "OFICIAL") -> dict[str, Any]:
    return {
        "id": source_id,
        "label": label,
        "snippet": snippet[:500],
        "url": url,
        "tipo": tipo,
    }


def build_municipal_assistant_context(db: Session, muni: Municipio) -> dict[str, Any]:
    ibge = db.query(MunicipioIbge).filter(MunicipioIbge.codigo_ibge == muni.codigo_ibge).first()
    fiscal = db.query(MunicipioFiscal).filter(MunicipioFiscal.codigo_ibge == muni.codigo_ibge).first()

    snapshot = executive_snapshot(db, muni)
    ranking, _ = build_bairro_ranking(db, muni)
    top3 = ranking[:3]

    try:
        maturity = compute_maturity(db, muni.codigo_ibge)
    except Exception:
        maturity = None

    capag_indicators: list[dict] = []
    nota_capag = fiscal.nota_capag if fiscal else None
    nota_capag_raw = None
    if fiscal and fiscal.raw_payload:
        try:
            payload = json.loads(fiscal.raw_payload)
            capag_indicators = payload.get("indicadores") or []
            nota_capag_raw = payload.get("nota_capag_raw")
        except (json.JSONDecodeError, TypeError):
            pass
    if not nota_capag:
        try:
            capag = collect_capag_municipality(muni.codigo_ibge)
            nota_capag = capag.get("nota_capag")
            nota_capag_raw = capag.get("nota_capag_raw")
            capag_indicators = capag.get("indicadores") or []
        except Exception:
            pass

    diag = (
        db.query(DiagnosticoExecutivo)
        .filter(DiagnosticoExecutivo.codigo_ibge == muni.codigo_ibge)
        .order_by(DiagnosticoExecutivo.gerado_em.desc())
        .first()
    )

    report = (
        db.query(RelatorioMunicipal)
        .filter(RelatorioMunicipal.codigo_ibge == muni.codigo_ibge, RelatorioMunicipal.status == "concluido")
        .order_by(RelatorioMunicipal.gerado_em.desc())
        .first()
    )

    pop = ibge.populacao if ibge and ibge.populacao else muni.populacao
    area = float(ibge.area_km2 if ibge and ibge.area_km2 else muni.area_km2 or 0)
    idh = float(ibge.idh) if ibge and ibge.idh else None
    pib_pc = float(ibge.pib_per_capita) if ibge and ibge.pib_per_capita else None

    sources: list[dict[str, Any]] = [
        _source(
            "ibge",
            "IBGE — Perfil demográfico",
            f"{muni.nome}/{muni.uf}: {pop:,} hab., {area:.1f} km², densidade {snapshot.get('densidade_demografica', 0):.0f} hab/km².",
            IBGE_FONTES,
        ),
        _source(
            "sinidu_score",
            "Sinidu+Clima — Score territorial",
            f"Score {snapshot.get('score_sinidu')}; IVC {snapshot.get('media_ivc')}; IRI {snapshot.get('media_iri')}; adaptação {snapshot.get('media_adaptacao')}.",
            "",
            "DERIVADO",
        ),
    ]

    if idh:
        sources.append(_source("ibge_idh", "IBGE — IDH", f"IDH municipal: {idh:.3f}.", IBGE_FONTES))
    if pib_pc:
        sources.append(_source("ibge_pib", "IBGE — PIB per capita", f"PIB per capita: R$ {pib_pc:,.2f}.", IBGE_FONTES))

    if nota_capag:
        cap_snip = f"CAPAG {nota_capag_raw or nota_capag}."
        for ind in capag_indicators[:3]:
            cap_snip += f" Ind.{ind.get('numero')} {ind.get('nome')}: nota {ind.get('nota')}."
        sources.append(_source("capag", "CAPAG / Tesouro Nacional", cap_snip, CAPAG_FONTES))

    if fiscal and fiscal.receita_corrente_liquida:
        sources.append(
            _source(
                "siconfi",
                "SICONFI — Saúde fiscal",
                f"RCL R$ {float(fiscal.receita_corrente_liquida):,.0f}; desp. pessoal {float(fiscal.despesa_pessoal_pct_rcl or 0):.1f}% RCL.",
                "https://siconfi.tesouro.gov.br/",
            )
        )

    if top3:
        bairros_txt = "; ".join(f"{r['bairro']} (score {r['score_sinidu']})" for r in top3)
        sources.append(
            _source(
                "sinidu_bairros",
                "Sinidu+Clima — Bairros prioritários",
                f"Top riscos: {bairros_txt}.",
                "",
                "DERIVADO",
            )
        )

    sources.append(
        _source(
            "s2id",
            "S2ID — Histórico de desastres",
            f"{snapshot.get('historico_desastres_count', 0)} eventos; danos materiais R$ {snapshot.get('danos_materiais_total', 0):,.0f}.",
            S2ID_FONTES,
        )
    )

    if maturity:
        sources.append(
            _source(
                "maturidade",
                "Motor de Maturidade Sinidu+Clima",
                f"Score {maturity['score']:.0f}/100 ({maturity['classificacao']}); faltantes: {', '.join(f['nome'] for f in maturity.get('fontes_faltantes', [])[:4]) or 'nenhum'}.",
                "",
                "DERIVADO",
            )
        )

    if diag:
        sources.append(
            _source(
                "diagnostico_executivo",
                f"Diagnóstico Executivo v{diag.versao}",
                diag.headline,
                "",
                "DERIVADO",
            )
        )

    if report:
        sources.append(
            _source(
                "relatorio_pdf",
                "Relatório territorial PDF",
                f"Último relatório: {report.nome_arquivo} ({report.gerado_em.strftime('%d/%m/%Y')}).",
                "",
                "DERIVADO",
            )
        )

    summary_lines = [
        f"MUNICÍPIO: {muni.nome}/{muni.uf} (IBGE {muni.codigo_ibge})",
        f"População: {pop:,} | Área: {area:.1f} km² | Densidade: {snapshot.get('densidade_demografica', 0):.0f} hab/km²",
    ]
    if idh:
        summary_lines.append(f"IDH: {idh:.3f}")
    if pib_pc:
        summary_lines.append(f"PIB per capita: R$ {pib_pc:,.2f}")

    summary_lines.extend([
        "",
        "RISCO CLIMÁTICO (Sinidu+Clima):",
        f"- Score municipal: {snapshot.get('score_sinidu')} (0–100, maior = maior prioridade)",
        f"- IVC médio: {snapshot.get('media_ivc')} | IRI médio: {snapshot.get('media_iri')} | Adaptação: {snapshot.get('media_adaptacao')}",
        f"- Cobertura vegetal: {snapshot.get('cobertura_vegetal_percent')}%",
        f"- Alertas CEMADEN: {snapshot.get('alertas_ativos_count')} | Eventos S2ID: {snapshot.get('historico_desastres_count')}",
    ])

    if top3:
        summary_lines.append("- Bairros prioritários:")
        for row in top3:
            summary_lines.append(
                f"  · {row['bairro']}: score {row['score_sinidu']}, IVC {row['ivc']}, IRI {row['iri']}"
            )

    summary_lines.append("")
    summary_lines.append("FISCAL / CAPAG:")
    summary_lines.append(f"- Nota CAPAG: {nota_capag_raw or nota_capag or 'não disponível'}")
    for ind in capag_indicators:
        val = ind.get("valor")
        val_txt = f"{float(val)*100:.1f}%" if val is not None else "—"
        summary_lines.append(f"- Indicador {ind.get('numero')} ({ind.get('nome')}): {val_txt}, nota {ind.get('nota') or '—'}")
    if fiscal and fiscal.receita_corrente_liquida:
        summary_lines.append(f"- RCL: R$ {float(fiscal.receita_corrente_liquida):,.0f}")

    if maturity:
        summary_lines.extend([
            "",
            "MATURIDADE DE DADOS:",
            f"- {maturity['score']:.0f}/100 — {maturity['classificacao']}",
        ])

    if diag:
        summary_lines.extend(["", "DIAGNÓSTICO EXECUTIVO:", f"- {diag.headline}"])

    if report:
        summary_lines.append(f"- Relatório PDF disponível: {report.nome_arquivo}")

    georedus_ctx = georedus_summary_for_context(db, muni.codigo_ibge)
    georedus_url = georedus_ctx.get("georedus_url") or georedus_municipio_url(muni.codigo_ibge)
    georedus_indicadores = georedus_ctx.get("georedus_indicadores") or []
    if georedus_ctx.get("georedus_summary"):
        summary_lines.extend(["", "REFERÊNCIA EXTERNA (lacunas locais):", georedus_ctx["georedus_summary"]])
        sources.append(
            _source(
                "georedus",
                "GeoReDUS — Catálogo nacional ReDUS",
                (
                    "Complemento para indicadores intramunicipais não integrados no Sinidu "
                    f"({len(georedus_indicadores)} sugestões para este município)."
                ),
                georedus_url,
                "REFERENCIA_EXTERNA",
            )
        )

    suggested = [
        f"Qual a nota CAPAG e a situação fiscal de {muni.nome}?",
        f"Quais bairros têm maior prioridade de intervenção em {muni.nome}?",
        "Resuma o diagnóstico executivo deste município.",
        "Quais programas federais de financiamento são compatíveis com este perfil?",
        "Qual a maturidade dos dados integrados e o que ainda falta?",
        "Quais ações estão no plano territorial prioritário?",
    ]
    if diag:
        suggested.insert(2, "Explique os principais riscos territoriais com base no diagnóstico salvo.")
    if georedus_ctx.get("tem_lacunas"):
        suggested.append("Quais dados ainda faltam localmente e onde consultar no GeoReDUS?")

    return {
        "codigo_ibge": muni.codigo_ibge,
        "municipio": {"nome": muni.nome, "uf": muni.uf},
        "headline": diag.headline if diag else f"Assistente municipal — {muni.nome}/{muni.uf}",
        "score_sinidu": snapshot.get("score_sinidu"),
        "nota_capag": nota_capag_raw or nota_capag,
        "maturidade": maturity["classificacao"] if maturity else None,
        "maturidade_score": round(maturity["score"]) if maturity else None,
        "summary_text": "\n".join(summary_lines),
        "sources": sources,
        "suggested_questions": suggested[:6],
        "tem_diagnostico": diag is not None,
        "tem_relatorio": report is not None,
        "georedus_url": georedus_url,
        "georedus_indicadores": georedus_indicadores,
    }


def format_context_for_prompt(ctx: dict[str, Any]) -> str:
    return ctx.get("summary_text") or ""


def format_sources_for_response(ctx: dict[str, Any]) -> list[dict[str, Any]]:
    return list(ctx.get("sources") or [])
