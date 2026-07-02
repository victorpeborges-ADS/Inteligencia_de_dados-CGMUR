#!/usr/bin/env python3
"""Supervisor de recarga batch — roda dentro do container backend (docker exec -d)."""

from __future__ import annotations

import argparse
import json
import logging
import sys
import time
from datetime import datetime
from pathlib import Path

import requests

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

DEFAULT_LIST = Path(__file__).resolve().parents[1] / "data" / "municipios_prioritarios.txt"
FONTES = ["malha_ibge", "socioeconomico_censo", "s2id", "cemaden", "seguranca_sinesp"]


def load_codes(path: Path, *, skip: int = 0) -> list[str]:
    lines = [ln.strip() for ln in path.read_text(encoding="utf-8").splitlines()]
    codes = [c for c in lines if c and not c.startswith("#")]
    return codes[skip:]


def poll_status(base: str, codigo: str, *, max_wait_s: int = 3600) -> str:
    deadline = time.monotonic() + max_wait_s
    while time.monotonic() < deadline:
        try:
            resp = requests.get(f"{base}/api/v1/municipios/{codigo}/status-recarga", timeout=30)
            resp.raise_for_status()
            status = resp.json().get("status", "unknown")
            if status in {"concluido", "erro"}:
                return status
        except requests.RequestException as exc:
            logger.warning("Poll %s: %s", codigo, exc)
        time.sleep(30)
    return "timeout"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base", default="http://127.0.0.1:8000")
    parser.add_argument("--list", type=Path, default=DEFAULT_LIST)
    parser.add_argument("--skip", type=int, default=0, help="Pular N primeiros municípios da lista")
    parser.add_argument("--pause", type=int, default=60, help="Pausa entre municípios (s)")
    args = parser.parse_args()

    codes = load_codes(args.list, skip=args.skip)
    logger.info("Batch: %d municípios (skip=%d)", len(codes), args.skip)

    for codigo in codes:
        logger.info("Recarregando %s...", codigo)
        try:
            resp = requests.post(
                f"{args.base}/api/v1/municipios/{codigo}/recarregar-dados-reais",
                json={"fontes": FONTES},
                timeout=60,
            )
            resp.raise_for_status()
        except requests.RequestException as exc:
            logger.error("POST %s falhou: %s", codigo, exc)
            continue

        status = poll_status(args.base, codigo)
        logger.info("%s → %s", codigo, status)

        if status == "concluido":
            try:
                aud = requests.get(f"{args.base}/api/v1/municipios/{codigo}/auditoria", timeout=30)
                if aud.ok:
                    a = aud.json()
                    logger.info(
                        "  %s — confiabilidade=%s malha=%s bairros=%s setores=%s",
                        a.get("nome"),
                        a.get("confiabilidade_geral"),
                        a.get("flag_malha"),
                        a.get("bairros_total"),
                        a.get("setores_total"),
                    )
            except requests.RequestException:
                pass

        time.sleep(args.pause)

    logger.info("Batch concluído.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
