"""Geração automática e persistência de planos de contingência."""

from __future__ import annotations

from app.timeutil import utc_now
from typing import Any

from shapely.geometry import mapping, shape
from shapely.ops import unary_union
from sqlalchemy.orm import Session

from app.models import (
    ContingencyPlan,
    ContingencyPlanRevision,
    EstabelecimentoSaude,
    InfraestruturaUrbana,
    Municipio,
)
from app.services.cobrade_templates import (
    cobrade_for_cenario,
    default_acoes_por_nivel,
    default_protocolo_campo,
    default_recursos_from_support,
)
from app.services.osrm_router import routes_from_zones_to_support_points


def _municipio_by_ibge(db: Session, codigo_ibge: str) -> Municipio | None:
    return db.query(Municipio).filter(Municipio.codigo_ibge == codigo_ibge).first()


def _snapshot_plan(plan: ContingencyPlan) -> dict:
    return {
        "cenario_tipo": plan.cenario_tipo,
        "nivel_alerta": plan.nivel_alerta,
        "zonas_evacuacao": plan.zonas_evacuacao,
        "rotas_fuga": plan.rotas_fuga,
        "pontos_apoio": plan.pontos_apoio,
        "contatos_defesa_civil": plan.contatos_defesa_civil,
        "acoes_por_nivel": plan.acoes_por_nivel,
        "recursos_operacionais": getattr(plan, "recursos_operacionais", None) or [],
        "protocolo_campo": getattr(plan, "protocolo_campo", None) or {},
        "cobrade_codigo": getattr(plan, "cobrade_codigo", None),
        "status": plan.status,
        "versao": plan.versao,
    }


def save_revision(db: Session, plan: ContingencyPlan, revisado_por: str = "sistema") -> None:
    rev = ContingencyPlanRevision(
        plan_id=plan.id,
        versao=plan.versao,
        snapshot=_snapshot_plan(plan),
        revisado_por=revisado_por,
    )
    db.add(rev)


def load_support_points(db: Session, municipio_id: int) -> list[dict]:
    points: list[dict] = []

    for est in db.query(EstabelecimentoSaude).filter(EstabelecimentoSaude.municipio_id == municipio_id).limit(40):
        if est.geom is None:
            continue
        from geoalchemy2.shape import to_shape
        pt = to_shape(est.geom)
        points.append({
            "nome": est.nome,
            "tipo": est.tipo,
            "cnes_codigo": est.cnes_codigo,
            "leitos_sus": est.leitos_sus,
            "fonte": "CNES",
            "coordinates": [pt.x, pt.y],
            "geometry": {"type": "Point", "coordinates": [pt.x, pt.y]},
        })

    for infra in (
        db.query(InfraestruturaUrbana)
        .filter(InfraestruturaUrbana.municipio_id == municipio_id)
        .filter(InfraestruturaUrbana.tipo.in_(["escola", "ginasio", "hospital", "ubs"]))
        .limit(30)
    ):
        if infra.geom is None:
            continue
        from geoalchemy2.shape import to_shape
        pt = to_shape(infra.geom)
        points.append({
            "nome": infra.nome,
            "tipo": infra.tipo,
            "fonte": "OSM/local",
            "coordinates": [pt.x, pt.y],
            "geometry": {"type": "Point", "coordinates": [pt.x, pt.y]},
        })

    if not points:
        points.append({
            "nome": "Ponto de apoio provisório — Praça central",
            "tipo": "abrigo_provisorio",
            "fonte": "template",
            "coordinates": [-34.877, -8.047],
            "geometry": {"type": "Point", "coordinates": [-34.877, -8.047]},
        })
    return points


def zones_from_risk_geometry(
    risk_geojson: dict,
    buffer_m: float = 500,
    default_capacity: int = 500,
) -> list[dict]:
    """Converte mancha de risco simulada em zonas de evacuação com buffer."""
    features = risk_geojson.get("features") or []
    if not features:
        return []

    geoms = []
    for f in features:
        try:
            geoms.append(shape(f["geometry"]))
        except Exception:
            continue
    if not geoms:
        return []

    merged = unary_union(geoms)
    # buffer aproximado em graus (~111km/deg); buffer_m metros
    buffered = merged.buffer(buffer_m / 111_000)
    if buffered.is_empty:
        return []

    parts = [buffered] if buffered.geom_type != "MultiPolygon" else list(buffered.geoms)
    zones = []
    for i, poly in enumerate(parts[:8]):
        c = poly.centroid
        zones.append({
            "nome": f"Zona de evacuação {i + 1}",
            "capacidade": default_capacity,
            "prioridade": i + 1,
            "centroid": [c.x, c.y],
            "geometry": mapping(poly),
        })
    return zones


def generate_plan_from_simulation(
    db: Session,
    codigo_ibge: str,
    cenario_tipo: str,
    risk_geojson: dict,
    buffer_m: float = 500,
    criado_por: str = "simulacao",
    simulacao_ref: dict | None = None,
    nivel_alerta: str | None = None,
) -> ContingencyPlan:
    from app.services.live_alert_level import live_alert_snapshot, normalize_nivel

    muni = _municipio_by_ibge(db, codigo_ibge)
    if not muni:
        raise ValueError(f"Município {codigo_ibge} não encontrado")

    zonas = zones_from_risk_geometry(risk_geojson, buffer_m=buffer_m)
    pontos = load_support_points(db, muni.id)
    rotas = routes_from_zones_to_support_points(zonas, pontos, uf=muni.uf)

    if nivel_alerta:
        nivel = normalize_nivel(nivel_alerta, default="AMARELO")
    else:
        live = live_alert_snapshot(db, codigo_ibge, hours=24)
        nivel = live["nivel_alerta"] if live.get("vivo") else "AMARELO"

    cobrade = cobrade_for_cenario(cenario_tipo)
    plan = ContingencyPlan(
        municipio_id=muni.id,
        cenario_tipo=cenario_tipo.upper(),
        nivel_alerta=nivel,
        criado_por=criado_por,
        zonas_evacuacao=zonas,
        rotas_fuga=rotas,
        pontos_apoio=pontos,
        contatos_defesa_civil=[
            {"nome": "Coordenação Defesa Civil", "cargo": "Coordenador / Plantão 24h", "telefone": "", "whatsapp": ""},
            {"nome": "Corpo de Bombeiros", "cargo": "CBM", "telefone": "193", "whatsapp": ""},
            {"nome": "SAMU", "cargo": "Regulação", "telefone": "192", "whatsapp": ""},
        ],
        acoes_por_nivel=default_acoes_por_nivel(cenario_tipo.upper()),
        recursos_operacionais=default_recursos_from_support(pontos),
        protocolo_campo=default_protocolo_campo(cenario_tipo.upper()),
        cobrade_codigo=cobrade.get("codigo"),
        status="RASCUNHO",
        versao=1,
        simulacao_ref=simulacao_ref,
    )
    db.add(plan)
    db.flush()
    save_revision(db, plan, criado_por)
    db.commit()
    db.refresh(plan)
    return plan


def update_plan(db: Session, plan_id: int, payload: dict, revisado_por: str = "usuario") -> ContingencyPlan:
    plan = db.query(ContingencyPlan).filter(ContingencyPlan.id == plan_id).first()
    if not plan:
        raise ValueError("Plano não encontrado")

    for field in (
        "cenario_tipo", "nivel_alerta", "zonas_evacuacao", "rotas_fuga",
        "pontos_apoio", "contatos_defesa_civil", "acoes_por_nivel", "status",
        "recursos_operacionais", "protocolo_campo", "cobrade_codigo",
    ):
        if field in payload and payload[field] is not None:
            setattr(plan, field, payload[field])

    plan.versao += 1
    plan.data_revisao = utc_now()
    plan.updated_at = utc_now()
    save_revision(db, plan, revisado_por)
    db.commit()
    db.refresh(plan)
    return plan


def plan_to_dict(plan: ContingencyPlan, muni: Municipio | None = None) -> dict[str, Any]:
    return {
        "id": plan.id,
        "municipio_id": plan.municipio_id,
        "codigo_ibge": muni.codigo_ibge if muni else None,
        "municipio_nome": muni.nome if muni else None,
        "cenario_tipo": plan.cenario_tipo,
        "nivel_alerta": plan.nivel_alerta,
        "data_criacao": plan.data_criacao.isoformat() if plan.data_criacao else None,
        "data_revisao": plan.data_revisao.isoformat() if plan.data_revisao else None,
        "criado_por": plan.criado_por,
        "zonas_evacuacao": plan.zonas_evacuacao,
        "rotas_fuga": plan.rotas_fuga,
        "pontos_apoio": plan.pontos_apoio,
        "contatos_defesa_civil": plan.contatos_defesa_civil,
        "acoes_por_nivel": plan.acoes_por_nivel,
        "recursos_operacionais": getattr(plan, "recursos_operacionais", None) or [],
        "protocolo_campo": getattr(plan, "protocolo_campo", None) or {},
        "cobrade_codigo": getattr(plan, "cobrade_codigo", None),
        "cobrade": cobrade_for_cenario(plan.cenario_tipo),
        "status": plan.status,
        "versao": plan.versao,
        "simulacao_ref": plan.simulacao_ref,
    }
