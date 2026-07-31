#!/usr/bin/env python3
"""Gera apresentacao-sinidu-keynote-light.html autocontida para compartilhamento (WhatsApp, e-mail)."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "docs" / "apresentacao-sinidu-keynote-light.source.html"
OUTPUT = ROOT / "docs" / "apresentacao-sinidu-keynote-light.html"
INLINE = ROOT / "scripts" / "inline_apresentacao_assets.py"


def main() -> int:
    if not SOURCE.is_file():
        print(f"Fonte ausente: {SOURCE}", file=sys.stderr)
        return 1

    cmd = [
        sys.executable,
        str(INLINE),
        "--source",
        str(SOURCE),
        "--output",
        str(OUTPUT),
    ]
    result = subprocess.run(cmd, cwd=ROOT)
    if result.returncode != 0:
        return result.returncode

    size_mb = OUTPUT.stat().st_size / (1024 * 1024)
    print()
    print("Arquivo para compartilhar:")
    print(f"  {OUTPUT}")
    print(f"  {size_mb:.1f} MB · 19 imagens embutidas em base64")
    print()
    print("WhatsApp: anexe o .html como documento (não use o .source.html).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
