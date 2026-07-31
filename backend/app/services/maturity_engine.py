"""Motor de maturidade municipal — score 0–100 a partir do estado real do banco."""

from __future__ import annotations

from app.timeutil import utc_now
from typing import Any

from sqlalchemy.orm import Session

from app.models import (
    AlertaCemaden,
    Bairro,
    CoberturaVegetalMapBiomas,
    HistoricoDesastreS2ID,
    Municipio,
    MunicipioFiscal,
    MunicipioIbge,
    MunicipioSaneamento,
    MunicipioSeed,
    WeatherForecastCache,
)
from app.services.mitigation_planner import PLAN_DIRECTOR_SOURCES

GENERIC_BAIRRO_NAMES = {
    "Centro",
    "Zona Norte",
    "Zona Sul",
    "Zona Leste",
    "Zona Oeste",
    "Periferia",
}

MATURITY_SOURCES = [
    {"id": "ibge", "nome": "IBGE", "grupo": "Demografia e territorio"},
    {"id": "siconfi", "nome": "SICONFI", "grupo": "Fiscal"},
    {"id": "capag", "nome": "CAPAG", "grupo": "Fiscal"},
    {"id": "s2id", "nome": "S2ID", "grupo": "Desastres"},
    {"id": "mapbiomas", "nome": "MapBiomas", "grupo": "Uso do solo"},
    {"id": "snis", "nome": "SNIS/SINISA", "grupo": "Saneamento"},
    {"id": "bairros", "nome": "Bairros", "grupo": "Territorio"},
    {"id": "plano_diretor", "nome": "Plano Diretor", "grupo": "Planejamento"},
    {"id": "dados_climaticos", "nome": "Dados Climaticos", "grupo": "Clima"},
]

STATUS_WEIGHT = {
    "OFICIAL": 1.0,
    "DERIVADO": 0.75,
    "ESTIMADO": 0.55,
    "LACUNA": 0.0,
}

TIER_THRESHOLDS = (
    (76, "Platina"),
    (51, "Ouro"),
    (26, "Prata"),
    (0, "Bronze"),
)

PRATA_MIN_SCORE = 26


def classify_tier(score: float) -> str:
    for threshold, label in TIER_THRESHOLDS:
        if score >= threshold:
            return label
    return "Bronze"


def _source_result(
    source_id: str,
    nome: str,
    grupo: str,
    status: str,
    *,
    detail: str = "",
    recomendacao: str = "",
) -> dict[str, Any]:
    weight = 100.0 / len(MATURITY_SOURCES)
    points = round(weight * STATUS_WEIGHT.get(status, 0.0), 2)
    return {
        "id": source_id,
        "nome": nome,
        "grupo": grupo,
        "status": status,
        "peso_percentual": round(weight, 2),
        "pontos": points,
        "detail": detail,
        "recomendacao": recomendacao or _default_recommendation(status, nome),
    }


def _default_recommendation(status: str, nome: str) -> str:
    if status == "OFICIAL":
        return f"Manter rotina de atualizacao para {nome}."
    if status == "DERIVADO":
        return f"Validar derivacao Sinidu+Clima de {nome} com fonte primaria."
    if status == "ESTIMADO":
        return f"Substituir estimativa de {nome} por carga oficial."
    return f"Integrar {nome} — dado ausente no municipio."


def _eval_ibge(db: Session, codigo_ibge: str) -> dict[str, Any]:
    row = db.query(MunicipioIbge).filter(MunicipioIbge.codigo_ibge == codigo_ibge).first()
    if row and row.populacao and row.area_km2:
        return _source_result(
            "ibge", "IBGE", "Demografia e territorio", "OFICIAL",
            detail=f"Pop. {row.populacao:,} · {float(row.area_km2):,.1f} km²".replace(",", "."),
        )
    muni = db.query(Municipio).filter(Municipio.codigo_ibge == codigo_ibge).first()
    if muni and muni.populacao:
        return _source_result(
            "ibge", "IBGE", "Demografia e territorio", "ESTIMADO",
            detail=f"Populacao municipal {muni.populacao:,} (indicadores SIDRA pendentes)".replace(",", "."),
        )
    return _source_result("ibge", "IBGE", "Demografia e territorio", "LACUNA")


def _eval_siconfi(db: Session, codigo_ibge: str) -> dict[str, Any]:
    row = db.query(MunicipioFiscal).filter(MunicipioFiscal.codigo_ibge == codigo_ibge).first()
    if row and row.receita_corrente_liquida:
        return _source_result(
            "siconfi", "SICONFI", "Fiscal", "OFICIAL",
            detail=f"RCL exercicio {row.exercicio or '—'}",
        )
    if row:
        return _source_result("siconfi", "SICONFI", "Fiscal", "ESTIMADO", detail="Registro fiscal parcial.")
    return _source_result("siconfi", "SICONFI", "Fiscal", "LACUNA")


def _eval_capag(db: Session, codigo_ibge: str) -> dict[str, Any]:
    row = db.query(MunicipioFiscal).filter(MunicipioFiscal.codigo_ibge == codigo_ibge).first()
    if row and row.nota_capag:
        return _source_result(
            "capag", "CAPAG", "Fiscal", "OFICIAL",
            detail=f"Nota {row.nota_capag}",
        )
    return _source_result("capag", "CAPAG", "Fiscal", "LACUNA", detail="Nota CAPAG nao disponivel.")


def _eval_s2id(db: Session, muni: Municipio | None, seed: MunicipioSeed | None) -> dict[str, Any]:
    if not muni:
        return _source_result("s2id", "S2ID", "Desastres", "LACUNA")
    count = db.query(HistoricoDesastreS2ID).filter(HistoricoDesastreS2ID.municipio_id == muni.id).count()
    if count == 0:
        return _source_result("s2id", "S2ID", "Desastres", "LACUNA")
    lacunas = (seed.lacunas or []) if seed else []
    steps = (seed.integration_steps or {}) if seed else {}
    s2id_step = steps.get("s2id", {})
    if "s2id_oficial" in lacunas or s2id_step.get("status") in ("parcial", "lacuna"):
        return _source_result(
            "s2id", "S2ID", "Desastres", "ESTIMADO",
            detail=f"{count} registro(s) territorial(is) estimados.",
        )
    return _source_result(
        "s2id", "S2ID", "Desastres", "OFICIAL",
        detail=f"{count} evento(s) historico(s).",
    )


def _eval_mapbiomas(db: Session, muni: Municipio | None) -> dict[str, Any]:
    if not muni:
        return _source_result("mapbiomas", "MapBiomas", "Uso do solo", "LACUNA")
    from app.models import MapBiomasMunicipalStat

    stats = (
        db.query(MapBiomasMunicipalStat)
        .filter(MapBiomasMunicipalStat.codigo_ibge == muni.codigo_ibge)
        .count()
    )
    official = (
        db.query(MapBiomasMunicipalStat)
        .filter(
            MapBiomasMunicipalStat.codigo_ibge == muni.codigo_ibge,
            MapBiomasMunicipalStat.data_quality.in_(("oficial", "referencia_mapbiomas")),
        )
        .count()
    )
    count = db.query(CoberturaVegetalMapBiomas).filter(CoberturaVegetalMapBiomas.municipio_id == muni.id).count()
    if official >= 6:
        return _source_result(
            "mapbiomas", "MapBiomas", "Uso do solo", "OFICIAL",
            detail=f"Série anual integrada ({stats} registros).",
        )
    if stats >= 6:
        return _source_result(
            "mapbiomas", "MapBiomas", "Uso do solo", "DERIVADO",
            detail=f"Série calibrada Sinidu+Clima ({stats} registros).",
        )
    if count >= 2:
        return _source_result("mapbiomas", "MapBiomas", "Uso do solo", "DERIVADO", detail=f"{count} poligono(s) de cobertura.")
    if count == 1:
        return _source_result("mapbiomas", "MapBiomas", "Uso do solo", "ESTIMADO", detail="Cobertura simplificada.")
    return _source_result("mapbiomas", "MapBiomas", "Uso do solo", "LACUNA")


def _eval_bairros(db: Session, muni: Municipio | None, seed: MunicipioSeed | None) -> dict[str, Any]:
    if not muni:
        return _source_result("bairros", "Bairros", "Territorio", "LACUNA")
    names = [b.nome for b in db.query(Bairro.nome).filter(Bairro.municipio_id == muni.id).all()]
    if not names:
        return _source_result("bairros", "Bairros", "Territorio", "LACUNA")
    generic_only = all(n in GENERIC_BAIRRO_NAMES for n in names)
    if generic_only or (seed and seed.geom_fonte == "lacuna_bbox"):
        return _source_result(
            "bairros", "Bairros", "Territorio", "ESTIMADO",
            detail=f"{len(names)} setores em grade estimada.",
        )
    if len(names) >= 4:
        return _source_result("bairros", "Bairros", "Territorio", "DERIVADO", detail=f"{len(names)} bairros mapeados.")
    return _source_result("bairros", "Bairros", "Territorio", "ESTIMADO", detail=f"{len(names)} bairro(s).")


def _eval_snis(db: Session, codigo_ibge: str) -> dict[str, Any]:
    row = db.query(MunicipioSaneamento).filter(MunicipioSaneamento.codigo_ibge == codigo_ibge).first()
    if not row:
        return _source_result("snis", "SNIS/SINISA", "Saneamento", "LACUNA")
    if row.data_quality == "oficial":
        detail = f"Agua {float(row.cobertura_agua_pct or 0):.0f}% · Esgoto {float(row.cobertura_esgoto_pct or 0):.0f}%"
        return _source_result("snis", "SNIS/SINISA", "Saneamento", "OFICIAL", detail=detail)
    return _source_result(
        "snis", "SNIS/SINISA", "Saneamento", "ESTIMADO",
        detail=f"Proxy UF · agua {float(row.cobertura_agua_pct or 0):.0f}%",
    )


def _eval_plano_diretor(codigo_ibge: str) -> dict[str, Any]:
    sources = PLAN_DIRECTOR_SOURCES.get(codigo_ibge)
    if sources:
        return _source_result(
            "plano_diretor", "Plano Diretor", "Planejamento", "OFICIAL",
            detail=sources[0].get("titulo", "Legislacao urbanistica catalogada."),
        )
    return _source_result(
        "plano_diretor", "Plano Diretor", "Planejamento", "LACUNA",
        detail="URL oficial nao catalogada para este municipio.",
    )


def _eval_clima(db: Session, codigo_ibge: str, muni: Municipio | None) -> dict[str, Any]:
    weather = (
        db.query(WeatherForecastCache)
        .filter(WeatherForecastCache.codigo_ibge == codigo_ibge)
        .order_by(WeatherForecastCache.fetched_at.desc())
        .first()
    )
    if weather:
        return _source_result(
            "dados_climaticos", "Dados Climaticos", "Clima", "DERIVADO",
            detail=f"OpenMeteo · precip 24h {float(weather.precip_24h_mm):.0f} mm",
        )
    if muni:
        alerts = db.query(AlertaCemaden).filter(AlertaCemaden.municipio_id == muni.id).count()
        if alerts > 0:
            return _source_result(
                "dados_climaticos", "Dados Climaticos", "Clima", "ESTIMADO",
                detail=f"{alerts} alerta(s) CEMADEN local(is).",
            )
    return _source_result("dados_climaticos", "Dados Climaticos", "Clima", "LACUNA")


def compute_maturity(db: Session, codigo_ibge: str) -> dict[str, Any]:
    code = str(codigo_ibge).zfill(7)[:7]
    muni = db.query(Municipio).filter(Municipio.codigo_ibge == code).first()
    seed = db.query(MunicipioSeed).filter(MunicipioSeed.codigo_ibge == code).first()

    fontes = [
        _eval_ibge(db, code),
        _eval_siconfi(db, code),
        _eval_capag(db, code),
        _eval_s2id(db, muni, seed),
        _eval_mapbiomas(db, muni),
        _eval_snis(db, code),
        _eval_bairros(db, muni, seed),
        _eval_plano_diretor(code),
        _eval_clima(db, code, muni),
    ]

    score = round(sum(f["pontos"] for f in fontes), 2)
    completeness = round(
        sum(1 for f in fontes if f["status"] != "LACUNA") / len(fontes) * 100,
        2,
    )
    tier = classify_tier(score)
    faltantes = [f for f in fontes if f["status"] == "LACUNA"]
    parciais = [f for f in fontes if f["status"] in ("ESTIMADO", "DERIVADO")]

    return {
        "codigo_ibge": code,
        "nome": muni.nome if muni else (seed.nome if seed else code),
        "uf": muni.uf if muni else (seed.uf if seed else "—"),
        "score": score,
        "completeness_score": completeness,
        "classificacao": tier,
        "fontes": fontes,
        "fontes_faltantes": [{"id": f["id"], "nome": f["nome"], "recomendacao": f["recomendacao"]} for f in faltantes],
        "fontes_parciais": [{"id": f["id"], "nome": f["nome"], "status": f["status"], "detail": f["detail"]} for f in parciais],
        "resumo": (
            f"Score {score:.0f}/100 ({tier}). "
            f"{len(faltantes)} fonte(s) ausente(s), {len(parciais)} parcial(is)/estimada(s)."
        ),
        "calculado_em": utc_now().isoformat(),
    }


def persist_maturity(db: Session, codigo_ibge: str) -> dict[str, Any]:
    result = compute_maturity(db, codigo_ibge)
    seed = db.query(MunicipioSeed).filter(MunicipioSeed.codigo_ibge == result["codigo_ibge"]).first()
    if seed:
        seed.maturity_score = result["score"]
        seed.completeness_score = result["completeness_score"]
        seed.updated_at = utc_now()
        lacunas = list(seed.lacunas or [])
        for f in result["fontes_faltantes"]:
            key = f"fonte_{f['id']}"
            if key not in lacunas:
                lacunas.append(key)
        seed.lacunas = lacunas
        db.commit()
    return result
