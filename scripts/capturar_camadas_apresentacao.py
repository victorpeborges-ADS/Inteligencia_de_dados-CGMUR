#!/usr/bin/env python3
"""Captura prints por camada/módulo — cada imagem com visual distinto."""

from __future__ import annotations

import sys
from pathlib import Path

try:
    from playwright.sync_api import sync_playwright, TimeoutError as PwTimeout
except ImportError:
    print("Instale: pip install playwright && playwright install chromium", file=sys.stderr)
    raise

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs" / "apresentacao-assets"
BASE = "http://localhost:3000"
VIEWPORT = {"width": 1440, "height": 900}

# grupo → rótulo exato no painel de camadas
LAYER_SHOTS: list[tuple[str, str, str | None]] = [
    ("camada-bairros", "Malha de Bairros", "Base"),
    ("camada-inundacao", "Risco de Inundação", "Clima e riscos"),
    ("camada-vulnerabilidade", "Vulnerabilidade Climática", "Clima e riscos"),
    ("camada-mapbiomas", "Uso do Solo (MapBiomas)", "Clima e riscos"),
    ("camada-s2id", "Histórico de Desastres (S2ID)", "Clima e riscos"),
    ("camada-alertas", "Alertas Ativos (CEMADEN)", "Clima e riscos"),
    ("camada-cruzar-riscos", "__preset__", None),
]


def wait_ready(page, extra_ms: int = 2500) -> None:
    page.wait_for_load_state("domcontentloaded", timeout=60_000)
    page.wait_for_timeout(extra_ms)


def expand_group(page, group: str) -> None:
    btn = page.locator("button").filter(has_text=group).first
    if not btn.count():
        return
    # grupos colapsados mostram ChevronRight no botão do grupo
    btn.click()
    page.wait_for_timeout(400)


def clear_layers(page) -> None:
    limpar = page.get_by_role("button", name="Limpar")
    if limpar.count():
        limpar.first.click(force=True)
        page.wait_for_timeout(600)


def shot_map(page, name: str) -> None:
    """Recorte do mapa 2D quando possível; senão viewport."""
    path = OUT / f"{name}.png"
    leaflet = page.locator(".leaflet-container").first
    mapbox = page.locator(".maplibregl-map").first
    if leaflet.count() and leaflet.is_visible():
        leaflet.screenshot(path=str(path))
    elif mapbox.count() and mapbox.is_visible():
        mapbox.screenshot(path=str(path))
    else:
        page.locator("div.relative.w-full.h-full.rounded-2xl").first.screenshot(path=str(path))
    print(f"  ✓ {path.name} ({path.stat().st_size // 1024} KB)")


def shot_page(page, name: str) -> None:
    path = OUT / f"{name}.png"
    page.screenshot(path=str(path), full_page=False)
    print(f"  ✓ {path.name} ({path.stat().st_size // 1024} KB)")


def ensure_layer_visible(page, label: str, group: str | None) -> None:
    layer = page.locator("button").filter(has_text=label).first
    if group and (not layer.count() or not layer.is_visible()):
        expand_group(page, group)


def set_only_layer(page, label: str, group: str | None) -> None:
    clear_layers(page)
    page.wait_for_timeout(400)
    if label == "__preset__":
        page.get_by_role("button", name="Cruzar riscos").click(force=True)
        return
    ensure_layer_visible(page, label, group)
    page.locator("button").filter(has_text=label).first.click(force=True)
    page.wait_for_timeout(400)
    # Garantir só limite municipal + camada alvo (sem malha de bairros, exceto no card de bairros)
    if label != "Malha de Bairros":
        bairros = page.locator("button").filter(has_text="Malha de Bairros").first
        if bairros.count():
            cls = bairros.get_attribute("class") or ""
            if "text-indigo-300" in cls or "font-bold" in cls:
                bairros.click(force=True)
                page.wait_for_timeout(300)
    if label == "Malha de Bairros":
        limite = page.locator("button").filter(has_text="Limite Municipal").first
        if limite.count():
            limite.click(force=True)
            page.wait_for_timeout(200)


def capture_layer(page, filename: str, label: str | None, group: str | None) -> None:
    page.goto(f"{BASE}/painel", wait_until="domcontentloaded", timeout=60_000)
    wait_ready(page, 3500)

    btn2d = page.get_by_role("button", name="Mapa 2D")
    if btn2d.count():
        btn2d.first.click(force=True)
        page.wait_for_timeout(500)

    set_only_layer(page, label or "", group)
    page.wait_for_timeout(5000)
    shot_page(page, filename)


def capture_simulacao(page) -> None:
    page.goto(f"{BASE}/simulacoes", wait_until="domcontentloaded", timeout=60_000)
    wait_ready(page, 3000)
    # Usa estado atual (painel de simulações visível) — evita espera de 60s+ no cálculo
    shot_page(page, "camada-simulacoes")
    terreno = page.get_by_role("button", name="Terreno 3D")
    if terreno.count():
        terreno.first.click(force=True)
        page.wait_for_timeout(3000)
    shot_map(page, "camada-simulacao-3d")


def capture_modulo(page, route: str, filename: str, extra_wait: int = 2500) -> None:
    page.goto(f"{BASE}{route}", wait_until="domcontentloaded", timeout=60_000)
    wait_ready(page, extra_wait)
    shot_page(page, filename)


def capture_comparador(page) -> None:
    page.goto(f"{BASE}/painel", wait_until="domcontentloaded", timeout=60_000)
    wait_ready(page, 3500)
    page.get_by_role("button", name="Comparar").first.click(force=True)
    page.wait_for_timeout(2000)
    shot_page(page, "comparador")


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    print("Capturando camadas distintas…")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport=VIEWPORT)
        page.set_default_timeout(90_000)

        for filename, label, group in LAYER_SHOTS:
            try:
                capture_layer(page, filename, label, group)
            except PwTimeout as exc:
                print(f"  ! timeout em {filename}: {exc}")

        try:
            capture_simulacao(page)
        except PwTimeout as exc:
            print(f"  ! timeout simulação: {exc}")

        for route, fname, wait in [
            ("/contingencia", "modulo-contingencia", 2500),
            ("/monitor", "modulo-monitor", 2500),
            ("/assistente", "modulo-assistente", 2500),
            ("/catalogo", "modulo-catalogo", 2500),
        ]:
            try:
                capture_modulo(page, route, fname, wait)
            except Exception as exc:
                print(f"  ! falha {fname}: {exc}")

        try:
            capture_comparador(page)
        except Exception as exc:
            print(f"  ! falha comparador: {exc}")

        browser.close()

    print(f"\nConcluído: {len(list(OUT.glob('camada-*.png')))} camadas + módulos em {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
