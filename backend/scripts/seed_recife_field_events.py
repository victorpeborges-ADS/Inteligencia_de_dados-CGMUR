"""Seed one-shot: eventos de campo Recife a partir das âncoras históricas."""
from __future__ import annotations

import datetime as dt
from collections import Counter

from app.db import SessionLocal
from app.models import EventoAlagamentoObservado
from app.services.evento_alagamento_service import create_field_event, list_observed_events
from app.services.rainfall_event_anchors import RECIFE_RAIN_ANCHORS

BAIRRO_XY = {
    "Santo Amaro": (-34.878, -8.055),
    "Afogados": (-34.908, -8.075),
    "Torre": (-34.905, -8.045),
    "Ibura": (-34.938, -8.125),
    "Cohab": (-34.948, -8.115),
    "Barro": (-34.955, -8.095),
    "Guabiraba": (-34.960, -8.000),
    "Tejipió": (-34.945, -8.090),
    "Casa Amarela": (-34.920, -8.025),
    "Passarinho": (-34.940, -7.995),
    "Dois Irmãos": (-34.955, -8.010),
    "Espinheiro": (-34.895, -8.045),
    "Graças": (-34.900, -8.040),
    "Boa Viagem": (-34.895, -8.120),
    "Imbiribeira": (-34.915, -8.110),
    "Centro": (-34.881, -8.054),
}

TIPO_MAP = {
    "inundacao_fluvial": ("Inundação", "fluvial"),
    "deslizamento_e_alagamento": ("Alagamento Urbano", "misto"),
    "deslizamento": ("Alagamento Urbano", "pluvial"),
    "alagamento_urbano": ("Alagamento Urbano", "pluvial"),
}

EXTRA_MAY = [
    ("2022-05-25", "Alagamento Urbano", "pluvial", 100.0, "Antecedente maio/2022 — série APAC/CEMADEN"),
    ("2022-05-26", "Alagamento Urbano", "pluvial", 120.0, "Antecedente maio/2022 — série APAC/CEMADEN"),
    ("2022-05-29", "Alagamento Urbano", "misto", 80.0, "Pós-pico maio/2022 — Defesa Civil/CEMADEN"),
    ("2022-05-30", "Alagamento Urbano", "misto", 60.0, "Pós-pico maio/2022 — Defesa Civil/CEMADEN"),
]


def main() -> None:
    db = SessionLocal()
    created = 0

    def seed_point(day, tipo, fen, lat, lng, precip, ref, sev="alta", pop=None):
        nonlocal created
        inicio = dt.datetime.fromisoformat(f"{day}T12:00:00")
        # evita duplicata óbvia mesmo dia+fonte+coords
        exists = (
            db.query(EventoAlagamentoObservado)
            .filter(
                EventoAlagamentoObservado.codigo_ibge == "2611606",
                EventoAlagamentoObservado.inicio_em == inicio,
                EventoAlagamentoObservado.fonte == "defesa_civil",
                EventoAlagamentoObservado.referencia == ref[:255],
            )
            .first()
        )
        if exists:
            return None
        create_field_event(
            db,
            codigo_ibge="2611606",
            tipo=tipo,
            inicio_em=inicio,
            severidade=sev,
            fenomeno=fen,
            populacao_afetada=pop,
            precip_acumulada_mm=precip,
            referencia=ref[:255],
            lat=lat,
            lng=lng,
            actor="seed_anchors_playbook",
        )
        created += 1
        return True

    for a in RECIFE_RAIN_ANCHORS:
        tipo, fen = TIPO_MAP.get(a["tipo_dominante"], ("Alagamento Urbano", "pluvial"))
        for b in (a.get("bairros") or ["Centro"])[:4]:
            lng, lat = BAIRRO_XY.get(b, (-34.88, -8.05))
            j = (hash(b) % 17) * 0.0001
            seed_point(
                a["data"],
                tipo,
                fen,
                lat + j,
                lng - j,
                float(a.get("precipitacao_mm") or 0),
                f"{a['label']} — {b} — {a.get('fonte')}",
                sev="critica" if (a.get("mortos_obs") or 0) > 0 else "alta",
                pop=int(a.get("populacao_afetada_obs") or 0) or None,
            )

    for day, tipo, fen, precip, ref in EXTRA_MAY:
        for b in ("Ibura", "Passarinho", "Afogados", "Casa Amarela"):
            lng, lat = BAIRRO_XY[b]
            seed_point(day, tipo, fen, lat, lng, precip, f"{ref} — {b}", sev="alta")

    summary = list_observed_events(db, "2611606", limit=200)
    c = Counter(
        r.fonte
        for r in db.query(EventoAlagamentoObservado).filter_by(codigo_ibge="2611606").all()
    )
    print("created_this_run", created)
    print("total_observados", summary["total"])
    print("fontes", dict(c))
    db.close()


if __name__ == "__main__":
    main()
