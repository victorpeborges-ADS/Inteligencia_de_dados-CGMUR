#!/usr/bin/env python3
"""Embute imagens locais em HTML de apresentação (base64) para compartilhamento offline."""

from __future__ import annotations

import argparse
import base64
import mimetypes
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"
DEFAULT_SOURCE = DOCS / "apresentacao-sinidu-keynote.source.html"
DEFAULT_OUTPUT = DOCS / "apresentacao-sinidu-keynote.html"
ASSET_PATTERN = re.compile(
    r"""(?P<attr>(?:src|href)=["'])(?P<path>apresentacao-assets/[^"']+)(?P<quote>["'])""",
    re.IGNORECASE,
)


def _mime_for(path: Path) -> str:
    guessed, _ = mimetypes.guess_type(path.name)
    return guessed or "application/octet-stream"


def inline_assets(html_path: Path, assets_dir: Path) -> tuple[str, int]:
    text = html_path.read_text(encoding="utf-8")
    replaced = 0
    cache: dict[str, str] = {}

    def _replace(match: re.Match[str]) -> str:
        nonlocal replaced
        rel = match.group("path")
        if rel in cache:
            data_uri = cache[rel]
        else:
            asset = assets_dir / Path(rel).name
            if not asset.is_file():
                print(f"  ! ausente: {rel}", file=sys.stderr)
                return match.group(0)
            payload = base64.b64encode(asset.read_bytes()).decode("ascii")
            data_uri = f"data:{_mime_for(asset)};base64,{payload}"
            cache[rel] = data_uri
            print(f"  ✓ {asset.name} ({asset.stat().st_size // 1024} KB)")
        replaced += 1
        return f'{match.group("attr")}{data_uri}{match.group("quote")}'

    updated = ASSET_PATTERN.sub(_replace, text)
    updated = updated.replace(' loading="lazy"', ' loading="eager"')

    remaining = ASSET_PATTERN.findall(updated)
    if remaining:
        print(f"ERRO: {len(remaining)} referência(s) apresentacao-assets/ não embutida(s).", file=sys.stderr)
        return updated, -1

    if "<!-- apresentacao: assets embutidos -->" not in updated:
        updated = updated.replace(
            "<head>",
            "<head>\n  <!-- apresentacao: assets embutidos — arquivo autocontido para compartilhamento offline -->",
            1,
        )
    return updated, replaced


def main() -> int:
    parser = argparse.ArgumentParser(description="Inline apresentacao-assets em HTML keynote")
    parser.add_argument(
        "--source",
        type=Path,
        default=DEFAULT_SOURCE,
        help="HTML fonte com caminhos relativos apresentacao-assets/",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT,
        help="HTML de saída autocontido (para compartilhar)",
    )
    parser.add_argument(
        "--assets-dir",
        type=Path,
        default=DOCS / "apresentacao-assets",
        help="Pasta com PNG/JPG",
    )
    args = parser.parse_args()

    if not args.source.is_file():
        print(f"HTML fonte não encontrado: {args.source}", file=sys.stderr)
        return 1
    if not args.assets_dir.is_dir():
        print(f"Pasta de assets não encontrada: {args.assets_dir}", file=sys.stderr)
        return 1

    print(f"Gerando {args.output.name} a partir de {args.source.name}…")
    updated, count = inline_assets(args.source, args.assets_dir)
    if count < 0:
        return 1
    if count == 0:
        print("Nenhuma referência apresentacao-assets/ encontrada.", file=sys.stderr)
        return 1

    args.output.write_text(updated, encoding="utf-8")
    size_mb = args.output.stat().st_size / (1024 * 1024)
    print(f"Concluído: {count} imagem(ns) embutida(s) — {size_mb:.1f} MB")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
