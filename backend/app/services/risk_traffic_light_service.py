"""Painel de risco único (semáforo) — Trilha A / 17h.1a + 17h.1b.

Consolida Score Sinidu, IVC, IRI, VM, alerta vivo e maturidade em um status
simples (VERDE / AMARELO / LARANJA / VERMELHO) por município e por bairro,
com flag explícita de modo baixa maturidade (bootstrap nacional).
"""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from sqlalchemy import func

from app.models import (
    Bairro,
    EscolaInep,
    EstabelecimentoSaude,
    Municipio,
    MunicipioSeed,
    TerritorioEspecial,
)
from app.services.analytical_engine import AnalyticalEngine
from app.services.catalog_coverage import coverage_for_code
from app.services.live_alert_level import live_alert_snapshot, max_alert_level, normalize_nivel
from app.services.maturity_engine import PRATA_MIN_SCORE, compute_maturity
from app.services.measures_catalog import recommend_measures
from app.services.municipal_profile_service import build_municipal_profile
from app.services.report_generator import build_bairro_ranking

# Score a partir do qual o bairro entra na exposição consolidada (LARANJA+)
EXPOSICAO_SCORE_MIN = 45

# Score Sinidu (0–100) → nível do semáforo (alinhado a action_plan_engine)
SCORE_THRESHOLDS = (
    (66, "VERMELHO"),
    (45, "LARANJA"),
    (33, "AMARELO"),
    (0, "VERDE"),
)

# Índices normalizados 0–1 → nível
INDEX_THRESHOLDS = (
    (0.66, "VERMELHO"),
    (0.45, "LARANJA"),
    (0.33, "AMARELO"),
    (0.0, "VERDE"),
)

NIVEL_LABEL = {
    "VERDE": "Baixo",
    "AMARELO": "Atenção",
    "LARANJA": "Elevado",
    "VERMELHO": "Crítico",
}

NIVEL_ACAO = {
    "VERDE": "Manutenção preventiva e monitoramento de rotina.",
    "AMARELO": "Priorizar áreas críticas e reforçar preparação operacional.",
    "LARANJA": "Ações de curto prazo e acompanhamento reforçado da Defesa Civil.",
    "VERMELHO": "Intervenção imediata — ativar contingência e priorizar recursos.",
}


def _nivel_from_score(score: float | int | None) -> str:
    if score is None:
        return "VERDE"
    value = float(score)
    for threshold, nivel in SCORE_THRESHOLDS:
        if value >= threshold:
            return nivel
    return "VERDE"


def _nivel_from_index(value: float | None) -> str:
    if value is None:
        return "VERDE"
    v = float(value)
    for threshold, nivel in INDEX_THRESHOLDS:
        if v >= threshold:
            return nivel
    return "VERDE"


def _component(
    *,
    id: str,
    nome: str,
    valor: float | int | None,
    escala: str,
    nivel: str,
    qualidade: str,
    detalhe: str = "",
) -> dict[str, Any]:
    return {
        "id": id,
        "nome": nome,
        "valor": valor,
        "escala": escala,
        "nivel": normalize_nivel(nivel),
        "label": NIVEL_LABEL.get(normalize_nivel(nivel), nivel),
        "qualidade": qualidade,
        "detalhe": detalhe,
    }


def _avg_vm(db: Session, municipio_id: int) -> tuple[float | None, int]:
    try:
        rows = AnalyticalEngine.calculate_multidimensional_vulnerability(db, municipio_id)
    except Exception:
        return None, 0
    if not rows:
        return None, 0
    values = [float(r.get("indice_vm", 0.0)) for r in rows if r.get("indice_vm") is not None]
    if not values:
        return None, 0
    return round(sum(values) / len(values), 3), len(values)


def _resolve_low_maturity(
    *,
    maturity: dict[str, Any],
    coverage_classificacao: str,
    coverage_pct: int,
    onboarding_status: str | None,
) -> dict[str, Any]:
    tier = str(maturity.get("classificacao") or maturity.get("tier") or "Bronze")
    maturity_score = float(maturity.get("score") or 0.0)
    bronze = tier == "Bronze" or maturity_score < PRATA_MIN_SCORE
    baixa_cobertura = coverage_classificacao == "Baixa" or coverage_pct < 50
    onboarding_aberto = (onboarding_status or "").lower() not in ("concluido", "concluído", "ok")

    ativo = bronze or baixa_cobertura or onboarding_aberto
    motivos: list[str] = []
    if bronze:
        motivos.append(f"Maturidade operacional {tier} (score {maturity_score:.0f}/100) — abaixo de Prata.")
    if baixa_cobertura:
        motivos.append(f"Cobertura do catálogo {coverage_pct}% (classificação Baixa).")
    if onboarding_aberto:
        motivos.append(f"Onboarding ainda em '{onboarding_status or 'pendente'}'.")

    aviso = (
        "Diagnóstico e simulações estão em modo bootstrap (dados nacionais: IBGE, S2ID, "
        "MapBiomas, CEMADEN, SRTM). Refino depende de dados locais e integração de fontes oficiais."
        if ativo
        else ""
    )

    return {
        "ativo": ativo,
        "aviso": aviso,
        "motivos": motivos,
        "maturidade_tier": tier,
        "maturidade_score": maturity_score,
        "cobertura_percentual": coverage_pct,
        "cobertura_classificacao": coverage_classificacao,
        "onboarding_status": onboarding_status or "pendente",
        "fontes_nacionais": ["ibge_cidades", "s2id", "mapbiomas", "cemaden_georiscos", "srtm_dem"],
    }


def _empty_exposicao(populacao: int | None = None) -> dict[str, Any]:
    return {
        "populacao": int(populacao or 0),
        "escolas": {"n": 0, "matriculas": 0},
        "saude": {"n": 0, "ubs": 0, "hospital": 0, "outros": 0},
        "territorios_especiais": {"n": 0, "tipos": [], "populacao_estimada": 0},
    }


def _exposicao_for_bairro(db: Session, bairro: Bairro, populacao_fallback: int | None) -> dict[str, Any]:
    """Agrega população e serviços oficiais no polígono do bairro (17h.2b)."""
    pop = int(bairro.pop_censo2022) if bairro.pop_censo2022 is not None else int(populacao_fallback or 0)
    expo = _empty_exposicao(pop)
    if bairro.geom is None:
        return expo

    try:
        escolas = (
            db.query(EscolaInep)
            .filter(
                EscolaInep.municipio_id == bairro.municipio_id,
                func.ST_Intersects(bairro.geom, EscolaInep.geom),
            )
            .all()
        )
        expo["escolas"] = {
            "n": len(escolas),
            "matriculas": int(sum(int(e.matriculas_total or 0) for e in escolas)),
        }
    except Exception:
        pass

    try:
        unidades = (
            db.query(EstabelecimentoSaude)
            .filter(
                EstabelecimentoSaude.municipio_id == bairro.municipio_id,
                func.ST_Intersects(bairro.geom, EstabelecimentoSaude.geom),
            )
            .all()
        )
        ubs = sum(1 for u in unidades if "ubs" in str(u.tipo or "").lower() or u.esf)
        hospital = sum(1 for u in unidades if "hospital" in str(u.tipo or "").lower())
        expo["saude"] = {
            "n": len(unidades),
            "ubs": ubs,
            "hospital": hospital,
            "outros": max(0, len(unidades) - ubs - hospital),
        }
    except Exception:
        pass

    try:
        territorios = (
            db.query(TerritorioEspecial)
            .filter(
                TerritorioEspecial.municipio_id == bairro.municipio_id,
                func.ST_Intersects(bairro.geom, TerritorioEspecial.geom),
            )
            .all()
        )
        tipos = sorted({str(t.tipo) for t in territorios if t.tipo})
        expo["territorios_especiais"] = {
            "n": len(territorios),
            "tipos": tipos,
            "populacao_estimada": int(sum(int(t.populacao_estimada or 0) for t in territorios)),
        }
    except Exception:
        pass

    return expo


def _sum_exposicao(items: list[dict[str, Any]]) -> dict[str, Any]:
    total = _empty_exposicao(0)
    tipos: set[str] = set()
    for e in items:
        total["populacao"] += int(e.get("populacao") or 0)
        esc = e.get("escolas") or {}
        total["escolas"]["n"] += int(esc.get("n") or 0)
        total["escolas"]["matriculas"] += int(esc.get("matriculas") or 0)
        sau = e.get("saude") or {}
        total["saude"]["n"] += int(sau.get("n") or 0)
        total["saude"]["ubs"] += int(sau.get("ubs") or 0)
        total["saude"]["hospital"] += int(sau.get("hospital") or 0)
        total["saude"]["outros"] += int(sau.get("outros") or 0)
        te = e.get("territorios_especiais") or {}
        total["territorios_especiais"]["n"] += int(te.get("n") or 0)
        total["territorios_especiais"]["populacao_estimada"] += int(te.get("populacao_estimada") or 0)
        for t in te.get("tipos") or []:
            tipos.add(str(t))
    total["territorios_especiais"]["tipos"] = sorted(tipos)
    return total


def _validacao_adapta(db: Session, muni: Municipio, media_adaptacao: float | None) -> dict[str, Any]:
    from app.services.adapta_brasil_validation_service import validate_against_adapta_brasil

    return validate_against_adapta_brasil(db, muni, media_adaptacao=media_adaptacao)


def build_risk_panel(db: Session, codigo_ibge: str, *, top_bairros: int = 8) -> dict[str, Any]:
    """Monta o painel de risco único para o município."""
    code = str(codigo_ibge).zfill(7)[:7]
    muni = db.query(Municipio).filter(Municipio.codigo_ibge == code).first()
    if not muni:
        raise ValueError(f"Município {code} não encontrado")

    ranking, snapshot = build_bairro_ranking(db, muni)
    avg_vm, vm_n = _avg_vm(db, muni.id)
    alerta = live_alert_snapshot(db, code)
    maturity = compute_maturity(db, code)
    coverage_pct, _bases, _gaps = coverage_for_code(code, db)
    coverage_class = "Alta" if coverage_pct >= 75 else ("Media" if coverage_pct >= 50 else "Baixa")

    seed = db.query(MunicipioSeed).filter(MunicipioSeed.codigo_ibge == code).first()
    onboarding_status = seed.onboarding_status if seed else None

    score = snapshot.get("score_sinidu")
    media_ivc = snapshot.get("media_ivc")
    media_iri = snapshot.get("media_iri")

    comp_score = _component(
        id="score",
        nome="Score Sinidu+Clima",
        valor=score,
        escala="0–100",
        nivel=_nivel_from_score(score),
        qualidade="Derivado",
        detalhe="45% IVC + 35% IRI + 20% déficit de adaptação",
    )
    comp_ivc = _component(
        id="ivc",
        nome="IVC médio",
        valor=media_ivc,
        escala="0–1",
        nivel=_nivel_from_index(media_ivc),
        qualidade="Derivado",
        detalhe="Vulnerabilidade climática agregada por bairro",
    )
    comp_iri = _component(
        id="iri",
        nome="IRI médio",
        valor=media_iri,
        escala="0–1",
        nivel=_nivel_from_index(media_iri),
        qualidade="Derivado",
        detalhe="Risco de inundação agregado por bairro",
    )
    comp_vm = _component(
        id="vm",
        nome="VM médio",
        valor=avg_vm,
        escala="0–1",
        nivel=_nivel_from_index(avg_vm),
        qualidade="Derivado" if avg_vm is not None else "Lacuna",
        detalhe=f"Vulnerabilidade multidimensional ({vm_n} setor(es))" if vm_n else "Sem setores para VM",
    )
    nivel_alerta = normalize_nivel(alerta.get("nivel_alerta"))
    comp_alerta = _component(
        id="alerta",
        nome="Alerta vivo",
        valor=None,
        escala="nível",
        nivel=nivel_alerta,
        qualidade="Oficial" if alerta.get("fonte") == "cemaden" else "Derivado",
        detalhe=(
            f"{alerta.get('cemaden_ativos_24h', 0)} CEMADEN / "
            f"{alerta.get('alertas_total_24h', 0)} alertas (24h)"
            + (f" · {alerta['titulo_recente']}" if alerta.get("titulo_recente") else "")
        ),
    )

    status = max_alert_level(
        [
            comp_score["nivel"],
            comp_ivc["nivel"],
            comp_iri["nivel"],
            comp_vm["nivel"],
            comp_alerta["nivel"],
        ]
    )

    bairro_by_id = {
        b.id: b
        for b in db.query(Bairro).filter(Bairro.municipio_id == muni.id).all()
    }

    bairros: list[dict[str, Any]] = []
    exposicoes_criticas: list[dict[str, Any]] = []
    for row in ranking[: max(1, top_bairros)]:
        nivel_b = _nivel_from_score(row.get("score_sinidu"))
        bairro_obj = bairro_by_id.get(row.get("bairro_id"))
        if bairro_obj is not None:
            exposicao = _exposicao_for_bairro(db, bairro_obj, row.get("populacao"))
        else:
            exposicao = _empty_exposicao(row.get("populacao"))

        entry = {
            "bairro": row["bairro"],
            "bairro_id": row.get("bairro_id"),
            "score_sinidu": row["score_sinidu"],
            "ivc": row["ivc"],
            "iri": row["iri"],
            "nivel": nivel_b,
            "label": NIVEL_LABEL.get(nivel_b, nivel_b),
            "componentes": row.get("componentes"),
            "fatores": row.get("fatores") or [],
            "fatores_principais": row.get("fatores_principais") or [],
            "exposicao": exposicao,
        }
        bairros.append(entry)
        if int(row.get("score_sinidu") or 0) >= EXPOSICAO_SCORE_MIN:
            exposicoes_criticas.append(exposicao)

    # Também soma exposição de bairros críticos fora do top (visão municipal)
    for row in ranking[max(1, top_bairros) :]:
        if int(row.get("score_sinidu") or 0) < EXPOSICAO_SCORE_MIN:
            continue
        bairro_obj = bairro_by_id.get(row.get("bairro_id"))
        if bairro_obj is None:
            continue
        exposicoes_criticas.append(_exposicao_for_bairro(db, bairro_obj, row.get("populacao")))

    n_criticos = sum(1 for r in ranking if int(r.get("score_sinidu") or 0) >= EXPOSICAO_SCORE_MIN)
    exposicao_resumo = _sum_exposicao(exposicoes_criticas)
    exposicao_resumo["bairros_criticos"] = n_criticos
    exposicao_resumo["limiar_score"] = EXPOSICAO_SCORE_MIN

    baixa = _resolve_low_maturity(
        maturity=maturity,
        coverage_classificacao=coverage_class,
        coverage_pct=int(coverage_pct),
        onboarding_status=onboarding_status,
    )

    perfil = build_municipal_profile(db, code, maturity=maturity)
    fatores_agregados: list[str] = []
    seen_f: set[str] = set()
    for row in bairros:
        for fid in row.get("fatores_principais") or []:
            if fid not in seen_f:
                seen_f.add(fid)
                fatores_agregados.append(fid)
    # IRI elevado também aciona medidas de drenagem
    if media_iri is not None and float(media_iri) >= 0.45 and "iri" not in seen_f:
        fatores_agregados.append("iri")

    medidas = recommend_measures(
        perfil,
        nivel_risco=status,
        fatores_principais=fatores_agregados,
        bairros_alvo=[b["bairro"] for b in bairros[:5]],
        limit=6,
    )

    hotspots: dict[str, Any] = {"total": 0, "hotspots": []}
    try:
        from app.services.recurring_hotspots_service import compute_recurring_hotspots

        hotspots = compute_recurring_hotspots(db, code, limit=8)
    except Exception:
        hotspots = {
            "codigo_ibge": code,
            "total": 0,
            "hotspots": [],
            "nota": "Hotspots recorrentes indisponíveis neste momento.",
        }

    return {
        "codigo_ibge": code,
        "nome": muni.nome,
        "uf": muni.uf,
        "status": status,
        "status_label": NIVEL_LABEL.get(status, status),
        "acao_sugerida": NIVEL_ACAO.get(status, ""),
        "componentes": {
            "score": comp_score,
            "ivc": comp_ivc,
            "iri": comp_iri,
            "vm": comp_vm,
            "alerta": comp_alerta,
        },
        "bairros": bairros,
        "bairros_total": len(ranking),
        "exposicao_resumo": exposicao_resumo,
        "hotspots_recorrentes": hotspots,
        "modo_baixa_maturidade": baixa,
        "perfil": perfil,
        "medidas_recomendadas": medidas,
        "snapshot": {
            "score_sinidu": score,
            "media_ivc": media_ivc,
            "media_iri": media_iri,
            "media_adaptacao": snapshot.get("media_adaptacao"),
            "alertas_ativos_count": snapshot.get("alertas_ativos_count"),
            "historico_desastres_count": snapshot.get("historico_desastres_count"),
            "populacao": snapshot.get("populacao"),
        },
        "validacao_adapta_brasil": _validacao_adapta(db, muni, snapshot.get("media_adaptacao")),
        "ciclo": "agir",
        "versao": "17g.2h",
    }
