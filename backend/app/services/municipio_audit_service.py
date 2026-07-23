"""Auditoria de qualidade e rastreabilidade do catálogo piloto."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.data_connectors.official_bairros_collector import is_official_ibge_mesh
from app.data_connectors.s2id_collector import s2id_quality_label
from app.data_connectors.territorial_mesh_collector import GENERIC_BAIRRO_NAMES
from app.models import (
    AlertaCemaden,
    Bairro,
    HistoricoDesastreS2ID,
    MapBiomasMunicipalStat,
    Municipio,
    MunicipioIbge,
    MunicipioSeguranca,
    MunicipioSeed,
    SetorCensitario,
)
from app.services.socioeconomic_engine import RECIFE_BAIRRO_RENDA

RECIFE_IBGE = "2611606"
OFFICIAL_MALHA_SOURCES = {"ibge_censo2022", "prefeitura_oficial", "ibge_censo2022_setores"}
REAL_SOCIO_SOURCES = {
    "ibge_censo2022_sidra",
    "ibge_ctm",
    "ibge_censo",
    "ibge_censo2022",
    "ctm_recife",
}
REAL_SEG_PREFIXES = ("sinesp", "dados.gov.br")


def _malha_stats(db: Session, muni: Municipio) -> dict[str, Any]:
    row = db.execute(
        text(
            """
            SELECT
                COUNT(*) AS total,
                COUNT(*) FILTER (
                    WHERE geom IS NOT NULL
                      AND ST_IsValid(geom)
                      AND ST_NPoints(geom) > 20
                ) AS validos_detalhados
            FROM bairros
            WHERE municipio_id = :mid
            """
        ),
        {"mid": muni.id},
    ).mappings().first()

    total = int(row["total"] or 0)
    validos = int(row["validos_detalhados"] or 0)

    seed = db.query(MunicipioSeed).filter(MunicipioSeed.codigo_ibge == muni.codigo_ibge).first()
    malha_fonte = getattr(seed, "malha_fonte", None) if seed else None

    com_fonte = 0
    fonte_vals: set[str] = set()
    try:
        fontes = db.query(Bairro.fonte_malha).filter(Bairro.municipio_id == muni.id).distinct().all()
        fonte_vals = {f[0] for f in fontes if f[0]}
        com_fonte = sum(1 for f in fonte_vals if f in OFFICIAL_MALHA_SOURCES)
    except Exception:
        pass

    if total == 0:
        flag = "MALHA_AUSENTE"
    elif (
        is_official_ibge_mesh(db, muni)
        or com_fonte > 0
        or malha_fonte in OFFICIAL_MALHA_SOURCES
        or fonte_vals & OFFICIAL_MALHA_SOURCES
    ):
        flag = "MALHA_OK"
    elif muni.codigo_ibge == RECIFE_IBGE and total >= 85:
        flag = "MALHA_OK"
        malha_fonte = malha_fonte or "prefeitura_oficial"
    else:
        names = {row[0] for row in db.query(Bairro.nome).filter(Bairro.municipio_id == muni.id).all()}
        if names and names <= GENERIC_BAIRRO_NAMES:
            flag = "MALHA_ESTIMADA"
        elif validos == 0 and total > 0:
            flag = "MALHA_ESTIMADA"
        else:
            flag = "MALHA_ESTIMADA"

    return {
        "flag_malha": flag,
        "bairros_total": total,
        "bairros_validos": validos,
        "malha_fonte": malha_fonte or ("ibge_censo2022" if flag == "MALHA_OK" else "estimado_sinidu"),
    }


def _socio_stats(db: Session, muni: Municipio) -> dict[str, Any]:
    setores = db.query(SetorCensitario).filter(SetorCensitario.municipio_id == muni.id).all()
    if not setores:
        return {"flag_socio": "SOCIOEC_AUSENTE", "setores_total": 0, "setores_reais": 0}

    real = 0
    for s in setores:
        fonte = (s.fonte_renda or "").lower()
        if fonte in REAL_SOCIO_SOURCES or fonte.startswith("ibge_censo"):
            real += 1
            continue
        if s.renda_media and float(s.renda_media) > 0 and fonte and "estim" not in fonte:
            real += 1

    if muni.codigo_ibge == RECIFE_IBGE and len(RECIFE_BAIRRO_RENDA) >= 80:
        return {
            "flag_socio": "SOCIOEC_REAL",
            "setores_total": len(setores),
            "setores_reais": len(setores),
            "fonte": "ctm_recife",
        }

    bairros_reais = 0
    try:
        bairros_reais = (
            db.query(Bairro)
            .filter(
                Bairro.municipio_id == muni.id,
                Bairro.renda_media_censo2022.isnot(None),
            )
            .count()
        )
    except Exception:
        bairros_reais = 0

    if bairros_reais > 0:
        return {
            "flag_socio": "SOCIOEC_REAL",
            "setores_total": len(setores),
            "setores_reais": max(real, bairros_reais),
            "fonte": "ibge_censo2022_sidra",
        }

    if real >= max(1, len(setores) // 2):
        return {
            "flag_socio": "SOCIOEC_REAL",
            "setores_total": len(setores),
            "setores_reais": real,
            "fonte": "ibge_parcial",
        }

    has_renda = any(float(s.renda_media or 0) > 0 for s in setores)
    if has_renda:
        return {
            "flag_socio": "SOCIOEC_ESTIMADO",
            "setores_total": len(setores),
            "setores_reais": real,
            "fonte": "estimativa_sinidu",
        }
    return {"flag_socio": "SOCIOEC_AUSENTE", "setores_total": len(setores), "setores_reais": 0}


def _seg_stats(db: Session, muni: Municipio) -> dict[str, Any]:
    rows = db.query(MunicipioSeguranca).filter(MunicipioSeguranca.codigo_ibge == muni.codigo_ibge).all()
    if not rows:
        return {"flag_seg": "SEG_AUSENTE", "registros": 0, "fonte": None}

    fontes = {(r.fonte or "").lower() for r in rows}
    if any("estimativa_sinidu" in f or f == "sintetico" for f in fontes):
        return {"flag_seg": "SEG_ESTIMADO", "registros": len(rows), "fonte": next(iter(fontes))}
    if any(any(p in f for p in REAL_SEG_PREFIXES) for f in fontes):
        return {"flag_seg": "SEG_REAL", "registros": len(rows), "fonte": next(iter(fontes))}
    return {"flag_seg": "SEG_ESTIMADO", "registros": len(rows), "fonte": next(iter(fontes))}


def _score_stats(db: Session, muni: Municipio, malha: dict, socio: dict, seg: dict) -> dict[str, Any]:
    campos: list[tuple[str, bool]] = [
        ("malha", malha["flag_malha"] == "MALHA_OK"),
        ("socioeconomico", socio["flag_socio"] == "SOCIOEC_REAL"),
        ("seguranca", seg["flag_seg"] == "SEG_REAL"),
        (
            "s2id",
            db.query(HistoricoDesastreS2ID).filter(HistoricoDesastreS2ID.municipio_id == muni.id).count() > 0
            and s2id_quality_label(db, muni) in {"Oficial", "Referencia"},
        ),
        ("cemaden", db.query(AlertaCemaden).filter(AlertaCemaden.municipio_id == muni.id).count() > 0),
        (
            "ibge",
            db.query(MunicipioIbge).filter(MunicipioIbge.codigo_ibge == muni.codigo_ibge).first() is not None,
        ),
        (
            "mapbiomas",
            db.query(MapBiomasMunicipalStat)
            .filter(MapBiomasMunicipalStat.codigo_ibge == muni.codigo_ibge)
            .count()
            > 0,
        ),
    ]

    total = len(campos)
    reais = sum(1 for _, ok in campos if ok)
    estimados = total - reais
    pct_real = round(100.0 * reais / total, 1) if total else 0.0
    pct_estimado = round(100.0 - pct_real, 1)

    flag_score = "SCORE_OK"
    if pct_estimado > 60:
        flag_score = "SCORE_BAIXA_CONFIANCA"

    seed = db.query(MunicipioSeed).filter(MunicipioSeed.codigo_ibge == muni.codigo_ibge).first()
    score_val = float(seed.score_sinidu) if seed and seed.score_sinidu is not None else None

    return {
        "flag_score": flag_score,
        "campos_reais": reais,
        "campos_estimados": estimados,
        "campos_reais_pct": pct_real,
        "score_sinidu": score_val,
    }


def _confiabilidade_geral(malha: dict, socio: dict, seg: dict, score: dict) -> str:
    if malha["flag_malha"] == "MALHA_AUSENTE":
        return "CRITICA"
    if malha["flag_malha"] == "MALHA_ESTIMADA" and score["flag_score"] == "SCORE_BAIXA_CONFIANCA":
        return "CRITICA"
    if malha["flag_malha"] == "MALHA_OK" and score["campos_reais_pct"] >= 55:
        return "ALTA"
    if malha["flag_malha"] == "MALHA_OK" and score["campos_reais_pct"] >= 35:
        return "MEDIA"
    if malha["flag_malha"] == "MALHA_ESTIMADA":
        return "BAIXA"
    return "MEDIA"


def audit_municipio(db: Session, muni: Municipio, *, persist: bool = False) -> dict[str, Any]:
    malha = _malha_stats(db, muni)
    socio = _socio_stats(db, muni)
    seg = _seg_stats(db, muni)
    score = _score_stats(db, muni, malha, socio, seg)
    confiabilidade = _confiabilidade_geral(malha, socio, seg, score)

    score_confiabilidade = "ALTA"
    if confiabilidade == "CRITICA":
        score_confiabilidade = "BAIXA"
    elif confiabilidade == "BAIXA" or score["campos_reais_pct"] < 40:
        score_confiabilidade = "ESTIMADO" if score["campos_reais_pct"] < 40 else "BAIXA"
    elif confiabilidade == "MEDIA":
        score_confiabilidade = "MEDIA"
    elif score["flag_score"] == "SCORE_BAIXA_CONFIANCA":
        score_confiabilidade = "MEDIA"

    result = {
        "codigo_ibge": muni.codigo_ibge,
        "nome": muni.nome,
        "uf": muni.uf,
        "flag_malha": malha["flag_malha"],
        "malha_fonte": malha["malha_fonte"],
        "bairros_total": malha["bairros_total"],
        "bairros_validos": malha["bairros_validos"],
        "flag_socio": socio["flag_socio"],
        "setores_total": socio.get("setores_total", 0),
        "setores_reais": socio.get("setores_reais", 0),
        "flag_seg": seg["flag_seg"],
        "seg_registros": seg["registros"],
        "seg_fonte": seg.get("fonte"),
        "flag_score": score["flag_score"],
        "campos_reais_pct": score["campos_reais_pct"],
        "score_sinidu": score["score_sinidu"],
        "score_confiabilidade": score_confiabilidade,
        "confiabilidade_geral": confiabilidade,
        "auditado_em": datetime.now(timezone.utc).isoformat(),
    }

    if persist:
        seed = db.query(MunicipioSeed).filter(MunicipioSeed.codigo_ibge == muni.codigo_ibge).first()
        if seed:
            try:
                seed.malha_fonte = malha["malha_fonte"]
                seed.score_confiabilidade = score_confiabilidade
                seed.auditoria_flags = {
                    k: result[k]
                    for k in (
                        "flag_malha",
                        "flag_socio",
                        "flag_seg",
                        "flag_score",
                        "confiabilidade_geral",
                        "campos_reais_pct",
                    )
                }
                seed.auditoria_at = datetime.now(timezone.utc)
                db.commit()
            except Exception:
                db.rollback()

    return result


def audit_all_municipios(
    db: Session,
    *,
    exclude_recife: bool = True,
    persist: bool = False,
) -> list[dict[str, Any]]:
    query = db.query(Municipio).order_by(Municipio.uf, Municipio.nome)
    if exclude_recife:
        query = query.filter(Municipio.codigo_ibge != RECIFE_IBGE)
    munis = query.all()
    return [audit_municipio(db, m, persist=persist) for m in munis]
