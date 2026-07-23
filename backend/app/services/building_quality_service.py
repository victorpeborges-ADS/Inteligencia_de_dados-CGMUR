"""Governança/qualidade 3D por edifício (17c.5).

Selos alinhados ao roadmap e à lógica Sinidu+Clima:
  LiDAR  → altura observada (nDSM / LiDAR local)
  OSM    → height ou building:levels do OpenStreetMap
  Estimado → heurística por uso / seed

`qualidade` permanece no vocabulário da plataforma:
  Oficial | Observado | Estimado | Derivado
"""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.models import Edificacao, Municipio

# selo_3d → (qualidade, confianca, label_curto, cor_hex sugerida)
SELO_META: dict[str, dict[str, str]] = {
    "LiDAR": {
        "qualidade": "Observado",
        "confianca": "alta",
        "label": "LiDAR / nDSM",
        "cor": "#10b981",
    },
    "OSM": {
        "qualidade": "Estimado",  # default; osm_height sobe para Observado
        "confianca": "media",
        "label": "OpenStreetMap",
        "cor": "#38bdf8",
    },
    "Estimado": {
        "qualidade": "Derivado",
        "confianca": "baixa",
        "label": "Estimado (heurística)",
        "cor": "#f59e0b",
    },
}

_FONTE_TO_SELO: dict[str, str] = {
    "ndsm_lidar": "LiDAR",
    "lidar": "LiDAR",
    "ndsm": "LiDAR",
    "osm_height": "OSM",
    "osm_levels": "OSM",
    "height": "OSM",
    "building:levels": "OSM",
    "osm": "OSM",
    "heuristic": "Estimado",
    "seed": "Estimado",
}


def selo_from_fonte(fonte_altura: str | None) -> str:
    key = (fonte_altura or "heuristic").strip().lower()
    if key in _FONTE_TO_SELO:
        return _FONTE_TO_SELO[key]
    if "lidar" in key or "ndsm" in key:
        return "LiDAR"
    if key.startswith("osm") or "level" in key or "height" in key:
        return "OSM"
    return "Estimado"


def qualidade_from_fonte(fonte_altura: str | None) -> str:
    """Qualidade canônica a partir da fonte de altura."""
    key = (fonte_altura or "heuristic").strip().lower()
    if key in {"ndsm_lidar", "lidar", "ndsm", "osm_height"}:
        return "Observado"
    if key in {"osm_levels", "height", "building:levels", "osm"}:
        return "Estimado"
    return "Derivado"


def resolve_building_seal(
    fonte_altura: str | None,
    *,
    qualidade: str | None = None,
) -> dict[str, Any]:
    """Metadados de selo para um edifício."""
    selo = selo_from_fonte(fonte_altura)
    meta = SELO_META[selo]
    q = qualidade_from_fonte(fonte_altura)
    # Se já houver qualidade explícita Observado em OSM height, preservar
    if qualidade and qualidade.strip() in {"Observado", "Oficial", "Estimado", "Derivado"}:
        # não rebaixar Observado vindo de nDSM/osm_height
        if qualidade.strip() == "Observado" and selo in {"LiDAR", "OSM"}:
            q = "Observado"
        elif selo == "Estimado":
            q = "Derivado"
        elif selo == "OSM" and q != "Observado":
            q = "Estimado"

    confianca = meta["confianca"]
    if q == "Observado":
        confianca = "alta"
    elif q == "Estimado":
        confianca = "media"
    else:
        confianca = "baixa"

    return {
        "selo_3d": selo,
        "selo_label": meta["label"],
        "qualidade": q,
        "confianca": confianca,
        "cor": meta["cor"],
        "fonte_altura": (fonte_altura or "heuristic"),
    }


def uso_grupo_from_uso(uso: str | None) -> str:
    """Tipologia agregada para materialização visual (17e.4)."""
    key = (uso or "").strip().lower()
    if key in {
        "apartments",
        "residential",
        "house",
        "detached",
        "semidetached_house",
        "terrace",
        "dormitory",
        "yes",
        "building",
    }:
        return "residencial"
    if key in {"commercial", "retail", "shop", "supermarket", "mall", "kiosk"}:
        return "comercial"
    if key in {"industrial", "warehouse", "manufacture", "factory"}:
        return "industrial"
    if key in {"office", "government", "civic", "public"}:
        return "escritorio"
    if key in {"school", "university", "college", "kindergarten"}:
        return "educacao"
    if key in {"hospital", "clinic", "doctors", "dentist"}:
        return "saude"
    if key in {"hotel", "hostel", "guest_house"}:
        return "hospedagem"
    if key in {
        "church",
        "cathedral",
        "chapel",
        "mosque",
        "temple",
        "synagogue",
        "religious",
    }:
        return "religioso"
    return "outro"


def enrich_feature_properties(props: dict[str, Any]) -> dict[str, Any]:
    """Injeta selo_3d / selo_label / confianca / uso_grupo em properties GeoJSON."""
    out = dict(props)
    seal = resolve_building_seal(out.get("fonte_altura"), qualidade=out.get("qualidade"))
    out["selo_3d"] = seal["selo_3d"]
    out["selo_label"] = seal["selo_label"]
    out["confianca"] = seal["confianca"]
    out["qualidade"] = seal["qualidade"]
    out["qualidade_dado"] = seal["qualidade"]
    out["_fill"] = seal["cor"]
    out["uso_grupo"] = uso_grupo_from_uso(out.get("uso"))
    return out


def apply_seal_to_row(row: Edificacao) -> bool:
    """Atualiza qualidade do row a partir de fonte_altura. Retorna True se mudou."""
    desired = qualidade_from_fonte(row.fonte_altura)
    if (row.qualidade or "") == desired:
        return False
    row.qualidade = desired
    return True


def normalize_municipality_quality(db: Session, codigo_ibge: str) -> dict[str, Any]:
    """Backfill de qualidade canônica para todas as edificações do município."""
    code = str(codigo_ibge).zfill(7)[:7]
    muni = db.query(Municipio).filter(Municipio.codigo_ibge == code).first()
    if not muni:
        raise ValueError(f"Município {code} não encontrado")

    rows = db.query(Edificacao).filter(Edificacao.municipio_id == muni.id).all()
    updated = 0
    by_selo: dict[str, int] = {}
    by_q: dict[str, int] = {}
    for row in rows:
        if apply_seal_to_row(row):
            updated += 1
        seal = resolve_building_seal(row.fonte_altura, qualidade=row.qualidade)
        by_selo[seal["selo_3d"]] = by_selo.get(seal["selo_3d"], 0) + 1
        by_q[seal["qualidade"]] = by_q.get(seal["qualidade"], 0) + 1

    if updated:
        db.commit()

    return {
        "codigo_ibge": code,
        "edificios": len(rows),
        "updated": updated,
        "por_selo_3d": by_selo,
        "por_qualidade": by_q,
        "selos": list(SELO_META.keys()),
        "padrao": "Oficial | Observado | Estimado | Derivado · selo_3d: LiDAR | OSM | Estimado",
    }


def quality_summary(db: Session, codigo_ibge: str) -> dict[str, Any]:
    """Resumo de governança 3D sem mutar dados."""
    code = str(codigo_ibge).zfill(7)[:7]
    muni = db.query(Municipio).filter(Municipio.codigo_ibge == code).first()
    if not muni:
        raise ValueError(f"Município {code} não encontrado")

    rows = (
        db.query(Edificacao.fonte_altura, Edificacao.qualidade)
        .filter(Edificacao.municipio_id == muni.id)
        .all()
    )
    by_selo: dict[str, int] = {}
    by_fonte: dict[str, int] = {}
    by_q: dict[str, int] = {}
    for fonte, qualidade in rows:
        seal = resolve_building_seal(fonte, qualidade=qualidade)
        by_selo[seal["selo_3d"]] = by_selo.get(seal["selo_3d"], 0) + 1
        by_fonte[fonte or "heuristic"] = by_fonte.get(fonte or "heuristic", 0) + 1
        by_q[seal["qualidade"]] = by_q.get(seal["qualidade"], 0) + 1

    total = len(rows)
    lidar_pct = round((by_selo.get("LiDAR", 0) / total) * 100) if total else 0
    return {
        "codigo_ibge": code,
        "edificios": total,
        "por_selo_3d": by_selo,
        "por_fonte_altura": by_fonte,
        "por_qualidade": by_q,
        "lidar_pct": lidar_pct,
        "legenda": [
            {"selo_3d": k, **{kk: vv for kk, vv in v.items() if kk != "qualidade"}, "qualidade_padrao": v["qualidade"]}
            for k, v in SELO_META.items()
        ],
        "padrao": "selo_3d: LiDAR | OSM | Estimado · qualidade: Observado | Estimado | Derivado",
    }
