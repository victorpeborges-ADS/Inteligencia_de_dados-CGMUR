#!/usr/bin/env python3
"""Captura screenshots da plataforma para docs/apresentacao-sinidu-keynote.html."""

from __future__ import annotations

import sys
import time
from pathlib import Path

try:
    from playwright.sync_api import sync_playwright
except ImportError:
    print("Instale: pip install playwright && playwright install chromium", file=sys.stderr)
    raise

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs" / "apresentacao-assets"
BASE = "http://localhost:3000"
MUNICIPIO = "2611606"  # Recife
VIEWPORT = {"width": 1440, "height": 900}


def wait_ready(page, extra_ms: int = 2500) -> None:
    page.wait_for_load_state("networkidle", timeout=90_000)
    page.wait_for_timeout(extra_ms)


def shot(page, name: str) -> None:
    path = OUT / f"{name}.png"
    page.screenshot(path=str(path), full_page=False)
    print(f"  ✓ {path.name} ({path.stat().st_size // 1024} KB)")


def safe_goto(page, url: str) -> bool:
    try:
        page.goto(url, wait_until="domcontentloaded", timeout=60_000)
        wait_ready(page)
        return True
    except Exception as exc:
        print(f"  ! falha em {url}: {exc}")
        return False


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport=VIEWPORT)
        page.set_default_timeout(90_000)

        print("Capturando prints Sinidu+Clima…")

        # Capa + mapa 2D (tela principal)
        page.goto(f"{BASE}/painel", wait_until="domcontentloaded")
        wait_ready(page, 4000)
        shot(page, "capa")
        shot(page, "mapa-2d")
        shot(page, "painel")

        # Simulações (+ mapa 3D após carregar painel)
        page.goto(f"{BASE}/simulacoes", wait_until="domcontentloaded")
        wait_ready(page, 3500)
        shot(page, "simulacoes")
        # Terreno 3D costuma aparecer no mapa central após hidratação
        page.wait_for_timeout(2000)
        shot(page, "mapa-3d")

        page.goto(f"{BASE}/contingencia", wait_until="domcontentloaded")
        wait_ready(page)
        shot(page, "contingencia")

        if safe_goto(page, f"{BASE}/monitor"):
            shot(page, "monitor")

        if safe_goto(page, f"{BASE}/assistente"):
            shot(page, "assistente")

        if safe_goto(page, f"{BASE}/apresentacao/{MUNICIPIO}"):
            wait_ready(page, 6000)
            shot(page, "relatorios")

        # Comparador — modal na central da oficina
        if safe_goto(page, f"{BASE}/painel"):
            wait_ready(page, 3000)
            compare_btn = page.get_by_role("button", name="Comparar")
            if compare_btn.count():
                compare_btn.first.click(force=True)
                page.wait_for_timeout(2000)
                shot(page, "comparador")
            else:
                print("  ! botão Comparar não encontrado — pulando comparador")

        browser.close()

    print(f"\nConcluído: {len(list(OUT.glob('*.png')))} imagens em {OUT}")

    import subprocess

    inline = ROOT / "scripts" / "inline_apresentacao_assets.py"
    if inline.is_file():
        print("\nGerando HTML autocontido para compartilhamento…")
        subprocess.run([sys.executable, str(inline)], check=False)
        subprocess.run(
            [
                sys.executable,
                str(inline),
                "--source",
                str(ROOT / "docs" / "apresentacao-sinidu3d-keynote.source.html"),
                "--output",
                str(ROOT / "docs" / "apresentacao-sinidu3d-keynote.html"),
            ],
            check=False,
        )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
