"""Seed: eventos de campo para Camutanga e Ilha de Itamaracá (pilotos PE LiDAR).

Uso:
  docker exec -w /app -e PYTHONPATH=/app sinidu_backend \\
    python scripts/seed_pe_lidar_field_events.py
"""
from __future__ import annotations

import datetime as dt
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from app.db import SessionLocal
from app.models import EventoAlagamentoObservado
from app.services.evento_alagamento_service import create_field_event

# (ibge, day, tipo, fenomeno, lat, lng, precip_mm, ref, pop)
EVENTS = [
    (
        "2603603",
        "2022-05-28",
        "Inundação",
        "pluvial",
        -7.4055,
        -35.2664,
        140.0,
        "Chuvas maio/2022 — sede Camutanga (Mata Norte)",
        400,
    ),
    (
        "2603603",
        "2017-05-27",
        "Alagamento Urbano",
        "pluvial",
        -7.4080,
        -35.2700,
        90.0,
        "Alagamento urbano — baixada sede Camutanga",
        200,
    ),
    (
        "2607604",
        "2022-05-28",
        "Inundação",
        "misto",
        -7.7470,
        -34.8250,
        160.0,
        "Chuvas maio/2022 — Ilha de Itamaracá / RMR",
        900,
    ),
    (
        "2607604",
        "2019-06-14",
        "Alagamento Urbano",
        "costeiro",
        -7.7600,
        -34.8400,
        70.0,
        "Maré + chuva — orla / centros Itamaracá",
        350,
    ),
]


def main() -> None:
    db = SessionLocal()
    created = 0
    try:
        for ibge, day, tipo, fen, lat, lng, precip, ref, pop in EVENTS:
            inicio = dt.datetime.fromisoformat(f"{day}T12:00:00")
            exists = (
                db.query(EventoAlagamentoObservado)
                .filter(
                    EventoAlagamentoObservado.codigo_ibge == ibge,
                    EventoAlagamentoObservado.inicio_em == inicio,
                    EventoAlagamentoObservado.fonte == "defesa_civil",
                    EventoAlagamentoObservado.referencia == ref[:255],
                )
                .first()
            )
            if exists:
                continue
            create_field_event(
                db,
                codigo_ibge=ibge,
                tipo=tipo,
                inicio_em=inicio,
                severidade="alta",
                fenomeno=fen,
                populacao_afetada=pop,
                precip_acumulada_mm=precip,
                referencia=ref[:255],
                lat=lat,
                lng=lng,
                actor="seed_pe_lidar",
            )
            created += 1
        print(f"seed_pe_lidar_field_events: created={created}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
