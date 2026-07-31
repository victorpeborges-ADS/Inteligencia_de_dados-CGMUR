"""Disseminação de alerta à população / Defesa Civil (17h.3d).

O Sinidu orquestra e audita; o município dispara pelos canais que já opera.
SMS massivo permanece stub até haver provider configurado.
"""

from __future__ import annotations

from app.timeutil import utc_now
import datetime
import logging
import os
import re
from typing import Any
from urllib.parse import quote

import httpx
from sqlalchemy.orm import Session

from app.models import ContingencyPlan, MonitoringAlert, Municipio
from app.services.cobrade_templates import PROTOCOLO_CAMPO_PADRAO
from app.services.gotify_notifier import push_risk_alert
from app.services.live_alert_level import live_alert_snapshot, normalize_nivel

logger = logging.getLogger(__name__)

DISPATCH_TIPO = "PUBLIC_ALERT_DISPATCH"

CANAL_IDS = (
    "checklist_dc",
    "whatsapp_dc",
    "gotify",
    "webhook",
    "sms",
)


def _digits(phone: str | None) -> str:
    return re.sub(r"\D+", "", str(phone or ""))


def _whatsapp_link(phone: str | None, text: str) -> str | None:
    digits = _digits(phone)
    if len(digits) < 10:
        return None
    if not digits.startswith("55") and len(digits) in (10, 11):
        digits = "55" + digits
    return f"https://wa.me/{digits}?text={quote(text[:900])}"


def _active_plan(db: Session, muni: Municipio) -> ContingencyPlan | None:
    from sqlalchemy import case

    return (
        db.query(ContingencyPlan)
        .filter(
            ContingencyPlan.municipio_id == muni.id,
            ContingencyPlan.status.in_(["ATIVO", "RASCUNHO"]),
        )
        .order_by(
            case((ContingencyPlan.status == "ATIVO", 0), else_=1),
            ContingencyPlan.updated_at.desc(),
        )
        .first()
    )


def build_draft_message(
    muni: Municipio,
    snap: dict[str, Any],
    *,
    nivel: str | None = None,
    mensagem_custom: str | None = None,
) -> str:
    if mensagem_custom and mensagem_custom.strip():
        return mensagem_custom.strip()[:2000]
    niv = normalize_nivel(nivel or snap.get("nivel_alerta"), default="AMARELO")
    titulo = snap.get("titulo_recente") or "Atenção da Defesa Civil"
    fonte = snap.get("fonte") or "monitoramento"
    return (
        f"[Sinidu+Clima · {niv}] {muni.nome}/{muni.uf}\n"
        f"{titulo}.\n"
        f"Fonte: {fonte}. IBGE {muni.codigo_ibge}.\n"
        f"Siga as orientações da Defesa Civil municipal. Evite áreas de risco."
    )


def list_available_channels(db: Session, muni: Municipio, mensagem: str) -> list[dict[str, Any]]:
    plan = _active_plan(db, muni)
    protocolo = dict((plan.protocolo_campo if plan else None) or PROTOCOLO_CAMPO_PADRAO)
    canais_dc = list(protocolo.get("canais") or PROTOCOLO_CAMPO_PADRAO["canais"])
    contatos = list((plan.contatos_defesa_civil if plan else None) or [])
    webhook = (
        (protocolo.get("webhook_url") if isinstance(protocolo.get("webhook_url"), str) else None)
        or os.getenv("PUBLIC_ALERT_WEBHOOK_URL", "").strip()
        or None
    )

    wa_destinos = []
    for c in contatos:
        if not isinstance(c, dict):
            continue
        phone = c.get("whatsapp") or c.get("telefone")
        link = _whatsapp_link(phone, mensagem)
        if link:
            wa_destinos.append({
                "nome": c.get("nome") or "Contato DC",
                "cargo": c.get("cargo"),
                "telefone": phone,
                "url": link,
            })

    gotify_ok = bool(os.getenv("GOTIFY_TOKEN", "").strip())

    return [
        {
            "id": "checklist_dc",
            "label": "Checklist Defesa Civil (sirene / rádio / redes)",
            "disponivel": True,
            "status_default": "registrado",
            "itens": canais_dc,
            "nota": "Marca canais institucionais como acionados — execução física no município.",
        },
        {
            "id": "whatsapp_dc",
            "label": "WhatsApp Defesa Civil",
            "disponivel": len(wa_destinos) > 0,
            "status_default": "link_gerado" if wa_destinos else "sem_contato",
            "destinos": wa_destinos,
            "nota": "Gera deep-link wa.me (sem API Meta). Abra no aparelho do operador.",
        },
        {
            "id": "gotify",
            "label": "Push equipe (Gotify)",
            "disponivel": gotify_ok,
            "status_default": "pronto" if gotify_ok else "nao_configurado",
            "nota": "Notifica operadores com GOTIFY_TOKEN configurado.",
        },
        {
            "id": "webhook",
            "label": "Webhook municipal",
            "disponivel": bool(webhook),
            "status_default": "pronto" if webhook else "nao_configurado",
            "url_configurada": bool(webhook),
            "nota": "POST JSON para PUBLIC_ALERT_WEBHOOK_URL ou protocolo_campo.webhook_url.",
        },
        {
            "id": "sms",
            "label": "SMS à população",
            "disponivel": False,
            "status_default": "nao_configurado",
            "nota": "Stub — aguarda gateway (Zenvia/Twilio) e base de assinantes municipal.",
        },
    ]


def draft_dissemination(db: Session, codigo_ibge: str) -> dict[str, Any]:
    code = str(codigo_ibge).zfill(7)[:7]
    muni = db.query(Municipio).filter(Municipio.codigo_ibge == code).first()
    if not muni:
        raise ValueError(f"Município {code} não encontrado")
    snap = live_alert_snapshot(db, code)
    mensagem = build_draft_message(muni, snap)
    plan = _active_plan(db, muni)
    return {
        "codigo_ibge": code,
        "nome": muni.nome,
        "uf": muni.uf,
        "nivel_sugerido": snap.get("nivel_alerta") or "AMARELO",
        "alerta_vivo": snap,
        "mensagem": mensagem,
        "canais": list_available_channels(db, muni, mensagem),
        "contingency_plan_id": plan.id if plan else None,
        "nota": (
            "Disseminação auditável: o Sinidu registra o acionamento; "
            "sirene/SMS/redes oficiais continuam sob responsabilidade da Defesa Civil."
        ),
    }


def _post_webhook(url: str, payload: dict[str, Any]) -> dict[str, Any]:
    try:
        with httpx.Client(timeout=8.0) as client:
            resp = client.post(url, json=payload)
            ok = resp.status_code < 400
            return {
                "status": "enviado" if ok else "falha",
                "http_status": resp.status_code,
                "detalhe": None if ok else resp.text[:200],
            }
    except Exception as exc:
        logger.warning("Webhook disseminação falhou: %s", exc)
        return {"status": "falha", "detalhe": str(exc)[:200]}


def dispatch_public_alert(
    db: Session,
    codigo_ibge: str,
    *,
    nivel: str | None = None,
    mensagem: str | None = None,
    canais: list[str] | None = None,
    checklist_itens: list[str] | None = None,
    criado_por: str = "gestor",
) -> dict[str, Any]:
    code = str(codigo_ibge).zfill(7)[:7]
    muni = db.query(Municipio).filter(Municipio.codigo_ibge == code).first()
    if not muni:
        raise ValueError(f"Município {code} não encontrado")

    snap = live_alert_snapshot(db, code)
    niv = normalize_nivel(nivel or snap.get("nivel_alerta"), default="AMARELO")
    msg = build_draft_message(muni, snap, nivel=niv, mensagem_custom=mensagem)
    available = {c["id"]: c for c in list_available_channels(db, muni, msg)}

    selected = [c for c in (canais or ["checklist_dc", "whatsapp_dc", "gotify"]) if c in CANAL_IDS]
    if not selected:
        selected = ["checklist_dc"]

    plan = _active_plan(db, muni)
    protocolo = dict((plan.protocolo_campo if plan else None) or PROTOCOLO_CAMPO_PADRAO)
    webhook_url = (
        (protocolo.get("webhook_url") if isinstance(protocolo.get("webhook_url"), str) else None)
        or os.getenv("PUBLIC_ALERT_WEBHOOK_URL", "").strip()
        or None
    )

    status_por_canal: dict[str, Any] = {}
    destinos: list[dict[str, Any]] = []

    if "checklist_dc" in selected:
        itens = checklist_itens or list(available["checklist_dc"].get("itens") or [])
        status_por_canal["checklist_dc"] = {
            "status": "acionado",
            "itens": itens,
            "em": utc_now().isoformat() + "Z",
        }

    if "whatsapp_dc" in selected:
        wa = available["whatsapp_dc"]
        if wa.get("disponivel"):
            destinos.extend(wa.get("destinos") or [])
            status_por_canal["whatsapp_dc"] = {
                "status": "link_gerado",
                "destinos": len(wa.get("destinos") or []),
            }
        else:
            status_por_canal["whatsapp_dc"] = {"status": "sem_contato"}

    if "gotify" in selected:
        ok = push_risk_alert(muni.nome, code, niv, msg)
        status_por_canal["gotify"] = {
            "status": "enviado" if ok else "nao_configurado_ou_falha",
        }

    if "webhook" in selected:
        if webhook_url:
            status_por_canal["webhook"] = _post_webhook(
                webhook_url,
                {
                    "tipo": DISPATCH_TIPO,
                    "codigo_ibge": code,
                    "municipio": muni.nome,
                    "uf": muni.uf,
                    "nivel": niv,
                    "mensagem": msg,
                    "criado_por": criado_por,
                    "timestamp": utc_now().isoformat() + "Z",
                },
            )
        else:
            status_por_canal["webhook"] = {"status": "nao_configurado"}

    if "sms" in selected:
        status_por_canal["sms"] = {
            "status": "nao_configurado",
            "nota": "Gateway SMS não integrado nesta versão.",
        }

    payload = {
        "canais": selected,
        "status_por_canal": status_por_canal,
        "destinos": destinos,
        "alerta_vivo": {
            "nivel": snap.get("nivel_alerta"),
            "fonte": snap.get("fonte"),
            "vivo": snap.get("vivo"),
        },
        "contingency_plan_id": plan.id if plan else None,
        "criado_por": criado_por,
    }

    row = MonitoringAlert(
        municipio_id=muni.id,
        codigo_ibge=code,
        tipo=DISPATCH_TIPO,
        nivel=niv,
        titulo=f"Disseminação DC · {niv}",
        mensagem=msg,
        payload=payload,
        expires_at=utc_now() + datetime.timedelta(hours=48),
    )
    db.add(row)
    db.commit()
    db.refresh(row)

    return {
        "id": row.id,
        "codigo_ibge": code,
        "nome": muni.nome,
        "uf": muni.uf,
        "nivel": niv,
        "mensagem": msg,
        "canais": selected,
        "status_por_canal": status_por_canal,
        "destinos": destinos,
        "contingency_plan_id": plan.id if plan else None,
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "tipo": DISPATCH_TIPO,
    }


def list_disseminations(db: Session, codigo_ibge: str, *, limit: int = 20) -> list[dict[str, Any]]:
    code = str(codigo_ibge).zfill(7)[:7]
    rows = (
        db.query(MonitoringAlert)
        .filter(MonitoringAlert.codigo_ibge == code, MonitoringAlert.tipo == DISPATCH_TIPO)
        .order_by(MonitoringAlert.created_at.desc())
        .limit(min(max(limit, 1), 50))
        .all()
    )
    out = []
    for r in rows:
        p = r.payload or {}
        out.append({
            "id": r.id,
            "nivel": r.nivel,
            "titulo": r.titulo,
            "mensagem": r.mensagem,
            "canais": p.get("canais") or [],
            "status_por_canal": p.get("status_por_canal") or {},
            "destinos": p.get("destinos") or [],
            "criado_por": p.get("criado_por"),
            "created_at": r.created_at.isoformat() if r.created_at else None,
        })
    return out
