#!/usr/bin/env python3
"""Gera a versão clara (light) da apresentação Sinidu keynote."""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "docs" / "apresentacao-sinidu-keynote.source.html"
OUT_SOURCE = ROOT / "docs" / "apresentacao-sinidu-keynote-light.source.html"
OUT_HTML = ROOT / "docs" / "apresentacao-sinidu-keynote-light.html"
INLINE_SCRIPT = ROOT / "scripts" / "inline_apresentacao_assets.py"

ROOT_BLOCK_OLD = """    :root {
      --bg: #09090b;
      --bg-elevated: #18181b;
      --card: #18181b;
      --border: #27272a;
      --text: #fafafa;
      --muted: #a1a1aa;
      --dim: #71717a;
      --accent: #6366f1;
      --accent-glow: rgba(99, 102, 241, 0.35);"""

ROOT_BLOCK_NEW = """    :root {
      --bg: #ffffff;
      --bg-elevated: #f8fafc;
      --card: #ffffff;
      --border: #e4e4e7;
      --text: #18181b;
      --muted: #52525b;
      --dim: #71717a;
      --accent: #4f46e5;
      --accent-glow: rgba(79, 70, 229, 0.22);"""

REPLACEMENTS: list[tuple[str, str]] = [
    (
        "<title>Sinidu+Clima — Demonstração funcional</title>",
        "<title>Sinidu+Clima — Demonstração funcional (versão clara)</title>",
    ),
    ("<html lang=\"pt-BR\">", "<html lang=\"pt-BR\" data-theme=\"light\">"),
    (ROOT_BLOCK_OLD, ROOT_BLOCK_NEW),
    ("::selection { background: rgba(129,140,248,0.35); }", "::selection { background: rgba(79,70,229,0.18); }"),
    (
        "background: linear-gradient(180deg, rgba(9,9,11,0.92) 0%, transparent 100%);",
        "background: linear-gradient(180deg, rgba(255,255,255,0.94) 0%, transparent 100%);",
    ),
    ("background: rgba(255,255,255,0.06);", "background: rgba(0,0,0,0.04);"),
    (
        ".btn-ghost:hover { background: rgba(255,255,255,0.1); border-color: rgba(255,255,255,0.15); }",
        ".btn-ghost:hover { background: rgba(0,0,0,0.06); border-color: rgba(0,0,0,0.12); }",
    ),
    ("background: rgba(255,255,255,0.15);", "background: rgba(0,0,0,0.12);"),
    (
        "background: radial-gradient(ellipse 70% 50% at 50% -20%, rgba(99,102,241,0.12), transparent 60%);",
        "background: radial-gradient(ellipse 70% 50% at 50% -20%, rgba(99,102,241,0.08), transparent 60%);",
    ),
    (
        "background: linear-gradient(180deg, #fff 0%, #a1a1aa 100%);",
        "background: linear-gradient(180deg, #18181b 0%, #52525b 100%);",
    ),
    (
        "0 0 0 1px rgba(255,255,255,0.03) inset,\n        0 40px 80px -20px rgba(0,0,0,0.7),",
        "0 0 0 1px rgba(0,0,0,0.05) inset,\n        0 24px 48px -16px rgba(0,0,0,0.12),",
    ),
    ("background: rgba(0,0,0,0.4);", "background: rgba(0,0,0,0.04);"),
    (".sidebar-mock {\n      background: #0a0a0c;", ".sidebar-mock {\n      background: #f4f4f5;"),
    (
        "linear-gradient(160deg, #0f172a, #09090b);",
        "linear-gradient(160deg, #e0f2fe, #f8fafc);",
    ),
    (".panel-mock {\n      background: #0a0a0c;", ".panel-mock {\n      background: #f4f4f5;"),
    (".kpi {\n      background: #141416;", ".kpi {\n      background: #ffffff;"),
    (".flow-item {\n      width: 100%;\n      text-align: center;\n      padding: 0.65rem 1.25rem;\n      background: var(--card);\n      border: 1px solid var(--border);\n      border-radius: 10px;\n      font-size: 0.85rem;\n      font-weight: 500;\n      color: #d4d4d8;", ".flow-item {\n      width: 100%;\n      text-align: center;\n      padding: 0.65rem 1.25rem;\n      background: var(--card);\n      border: 1px solid var(--border);\n      border-radius: 10px;\n      font-size: 0.85rem;\n      font-weight: 500;\n      color: #3f3f46;"),
    ("      color: #fff;\n      font-weight: 600;\n      box-shadow: 0 0 30px -10px var(--accent-glow);", "      color: var(--text);\n      font-weight: 600;\n      box-shadow: 0 0 30px -10px var(--accent-glow);"),
    ("box-shadow: 0 20px 40px -20px rgba(0,0,0,0.5);", "box-shadow: 0 16px 32px -20px rgba(0,0,0,0.1);"),
    (".module-card .module-do strong { color: #d4d4d8; font-weight: 600; }", ".module-card .module-do strong { color: #27272a; font-weight: 600; }"),
    (".showcase-visual.map2d {\n      background: linear-gradient(135deg, #0f172a, #1e1b4b);", ".showcase-visual.map2d {\n      background: linear-gradient(135deg, #e0e7ff, #eef2ff);"),
    (
        ".showcase-visual.map3d {\n      background: linear-gradient(180deg, #1e293b 0%, #0f172a 60%, #020617 100%);",
        ".showcase-visual.map3d {\n      background: linear-gradient(180deg, #f1f5f9 0%, #e2e8f0 60%, #cbd5e1 100%);",
    ),
    (".showcase-visual.layers {\n      background: #09090b;", ".showcase-visual.layers {\n      background: #f8fafc;"),
    (".layer-row {\n      display: flex;\n      justify-content: space-between;\n      align-items: center;\n      padding: 8px 10px;\n      background: #141416;", ".layer-row {\n      display: flex;\n      justify-content: space-between;\n      align-items: center;\n      padding: 8px 10px;\n      background: #ffffff;"),
    (".showcase-visual.sim {\n      background: #0f172a;", ".showcase-visual.sim {\n      background: #f1f5f9;"),
    (
        ".showcase-visual.cont {\n      background: linear-gradient(135deg, #1c1917, #292524);",
        ".showcase-visual.cont {\n      background: linear-gradient(135deg, #fff7ed, #fef2f2);",
    ),
    (".showcase-visual.mon {\n      background: #09090b;", ".showcase-visual.mon {\n      background: #f8fafc;"),
    (".showcase-visual.cmp {\n      background: #0a0a0c;", ".showcase-visual.cmp {\n      background: #f4f4f5;"),
    (".cmp-col {\n      background: #141416;", ".cmp-col {\n      background: #ffffff;"),
    (
        "background: linear-gradient(135deg, #fff, var(--accent));",
        "background: linear-gradient(135deg, #18181b, var(--accent));",
    ),
    ("background: rgba(255,255,255,0.03);", "background: rgba(0,0,0,0.02);"),
    (".action-list li {\n      padding: 0.55rem 0;\n      padding-left: 1.25rem;\n      position: relative;\n      color: #d4d4d8;", ".action-list li {\n      padding: 0.55rem 0;\n      padding-left: 1.25rem;\n      position: relative;\n      color: #3f3f46;"),
    (".status-next { background: rgba(99,102,241,0.12); color: #a5b4fc;", ".status-next { background: rgba(99,102,241,0.1); color: #4338ca;"),
    (".vision-quote {\n      font-family: \"Instrument Serif\", Georgia, serif;\n      font-size: clamp(1.5rem, 3.5vw, 2.25rem);\n      line-height: 1.45;\n      max-width: 800px;\n      margin: 0 auto;\n      font-style: italic;\n      color: #e4e4e7;", ".vision-quote {\n      font-family: \"Instrument Serif\", Georgia, serif;\n      font-size: clamp(1.5rem, 3.5vw, 2.25rem);\n      line-height: 1.45;\n      max-width: 800px;\n      margin: 0 auto;\n      font-style: italic;\n      color: #3f3f46;"),
    ('style="color:#fff"', 'style="color:var(--text)"'),
    ('style="color:#e4e4e7; font-weight:500"', 'style="color:#3f3f46; font-weight:500"'),
]


def apply_light_theme(text: str) -> str:
    for old, new in REPLACEMENTS:
        if old not in text:
            raise SystemExit(f"Trecho não encontrado para light theme:\n{old[:120]}…")
        text = text.replace(old, new)
    if "<!-- apresentacao: tema claro -->" not in text:
        text = text.replace("<head>", "<head>\n  <!-- apresentacao: tema claro -->", 1)
    return text


def main() -> int:
    if not SOURCE.is_file():
        print(f"Fonte ausente: {SOURCE}", file=sys.stderr)
        return 1

    light_source = apply_light_theme(SOURCE.read_text(encoding="utf-8"))
    OUT_SOURCE.write_text(light_source, encoding="utf-8")
    print(f"✓ {OUT_SOURCE.relative_to(ROOT)}")

    cmd = [
        sys.executable,
        str(INLINE_SCRIPT),
        "--source",
        str(OUT_SOURCE),
        "--output",
        str(OUT_HTML),
    ]
    print("Embutindo assets…")
    result = subprocess.run(cmd, cwd=ROOT, check=False)
    if result.returncode != 0:
        return result.returncode
    print(f"✓ {OUT_HTML.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
