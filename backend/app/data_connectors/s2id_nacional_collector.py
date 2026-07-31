"""Ingestão S2ID nacional via CSVs abertos MIDR/SEDEC (Fase 21c.1).

Fonte CKAN: https://dadosabertos.mdr.gov.br/dataset/s2id_sedec
CSVs anuais (encoding latin-1, sep ';', cabeçalho após linhas de título).
Protocolo tipicamente: UF-F-{IBGE7}-{COBRADE}-{YYYYMMDD}
"""

from __future__ import annotations

import csv
import datetime as dt
import io
import logging
import re
from pathlib import Path
from typing import Any, Iterable

import httpx
from sqlalchemy.orm import Session

from app.models import HistoricoDesastreS2ID, Municipio
from ml.constants import ML_TARGET_IBGE_CODES

logger = logging.getLogger(__name__)

CKAN_PACKAGE = "https://dadosabertos.mdr.gov.br/api/3/action/package_show?id=s2id_sedec"

# COBRADE hidrológicos / chuvas intensas (prefixos)
FLOOD_COBRADE_PREFIXES = (
    "12100",  # Inundações
    "12101",
    "12102",
    "12200",  # Enxurradas
    "12201",
    "12300",  # Alagamentos
    "12301",
    "13214",  # Chuvas Intensas
    "13215",
)

TIPO_BY_PREFIX = {
    "121": "Inundação",
    "122": "Enxurrada",
    "123": "Alagamento Urbano",
    "132": "Alagamento Urbano",  # chuvas intensas → impacto urbano
}

PROTOCOLO_IBGE_RE = re.compile(r"(?:^|-)(\d{7})(?:-|$)")
COBRADE_RE = re.compile(r"(\d{5})")


def _downloads_dir() -> Path:
    """Resolve pasta de CSVs (local: repo/scripts; Docker: /data ou env)."""
    import os

    override = (os.getenv("S2ID_NACIONAL_DOWNLOADS") or "").strip()
    if override:
        root = Path(override)
        root.mkdir(parents=True, exist_ok=True)
        return root

    here = Path(__file__).resolve()
    backend_root = here.parents[2]  # .../backend (dev) ou /app (Docker)
    parent = backend_root.parent
    repo_scripts = parent / "scripts" / "s2id_nacional" / "downloads"
    # Só usa layout monorepo se o parent parecer o repositório (não "/" do Docker)
    looks_like_repo = backend_root.name == "backend" or (
        (parent / "docker-compose.yml").is_file() and (parent / "scripts").is_dir()
    )
    if looks_like_repo:
        repo_scripts.mkdir(parents=True, exist_ok=True)
        return repo_scripts

    data = Path(os.getenv("SINIDU_DATA_DIR", "/data")) / "s2id_nacional" / "downloads"
    data.mkdir(parents=True, exist_ok=True)
    return data


def list_ckan_csv_resources(timeout: float = 60.0) -> list[dict[str, Any]]:
    with httpx.Client(timeout=timeout, follow_redirects=True) as client:
        resp = client.get(CKAN_PACKAGE)
        resp.raise_for_status()
        payload = resp.json()
    resources = payload.get("result", {}).get("resources") or []
    out = []
    for r in resources:
        fmt = (r.get("format") or "").upper()
        name = r.get("name") or r.get("url") or ""
        url = r.get("url") or ""
        if fmt == "CSV" or url.lower().endswith(".csv"):
            out.append({
                "id": r.get("id"),
                "name": name,
                "url": url,
                "year": _year_from_name(name + " " + url),
            })
    out.sort(key=lambda x: (x.get("year") or 0, x.get("name") or ""))
    return out


def _year_from_name(text: str) -> int | None:
    m = re.search(r"(20\d{2})", text)
    return int(m.group(1)) if m else None


def _looks_like_csv(raw: bytes) -> bool:
    if not raw or len(raw) < 200:
        return False
    head = raw[:400].lstrip().lower()
    if head.startswith(b"<html") or b"request rejected" in head:
        return False
    text = _decode_csv_text(raw[:2000])
    return ";" in text or "," in text


def download_csv(url: str, *, force: bool = False, timeout: float = 120.0) -> Path:
    year = _year_from_name(url) or "unknown"
    dest = _downloads_dir() / f"s2id_{year}.csv"
    if dest.exists() and dest.stat().st_size > 1000 and not force and _looks_like_csv(dest.read_bytes()[:800]):
        return dest

    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        ),
        "Accept": "text/csv,application/octet-stream,*/*;q=0.8",
        "Referer": "https://dadosabertos.mdr.gov.br/dataset/s2id_sedec",
    }
    with httpx.Client(timeout=timeout, follow_redirects=True, headers=headers) as client:
        resp = client.get(url)
        resp.raise_for_status()
        if not _looks_like_csv(resp.content):
            raise RuntimeError(
                f"Download S2ID bloqueado ou inválido (WAF/HTML) para {url}. "
                f"Baixe manualmente o CSV e coloque em {dest}"
            )
        dest.write_bytes(resp.content)
    return dest


def _decode_csv_text(raw: bytes) -> str:
    for enc in ("latin-1", "cp1252", "utf-8"):
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            continue
    return raw.decode("latin-1", errors="replace")


def _find_header_line(lines: list[str]) -> int:
    for i, line in enumerate(lines[:20]):
        upper = line.upper()
        if "UF;" in upper and ("MUNIC" in upper or "COBRADE" in upper or "PROTOCOLO" in upper):
            return i
        if "UF," in upper and "MUNIC" in upper:
            return i
    return 0


def _parse_date(value: str) -> dt.date | None:
    v = (value or "").strip()
    if not v:
        return None
    for fmt in ("%d/%m/%Y", "%Y-%m-%d", "%Y%m%d", "%d-%m-%Y"):
        try:
            return dt.datetime.strptime(v[:10] if len(v) >= 8 else v, fmt).date()
        except ValueError:
            continue
    digits = re.sub(r"\D", "", v)
    if len(digits) >= 8:
        try:
            return dt.datetime.strptime(digits[:8], "%Y%m%d").date()
        except ValueError:
            return None
    return None


def _ibge_from_row(row: dict[str, str]) -> str | None:
    for key in ("Código IBGE", "Codigo IBGE", "COD_IBGE", "cod_ibge", "IBGE"):
        if key in row and row[key]:
            digits = re.sub(r"\D", "", row[key])
            if len(digits) >= 7:
                return digits[:7]
    protocolo = row.get("Protocolo") or row.get("protocolo") or row.get("Registro") or ""
    m = PROTOCOLO_IBGE_RE.search(protocolo)
    if m:
        return m.group(1)
    # Padrão UF-F-XXXXXXX-...
    parts = protocolo.split("-")
    for p in parts:
        if p.isdigit() and len(p) == 7:
            return p
    return None


def _cobrade_code(row: dict[str, str]) -> str | None:
    for key in ("COBRADE", "CobradE", "Cobrade", "Código COBRADE", "Codigo COBRADE"):
        if key in row and row[key]:
            m = COBRADE_RE.search(row[key])
            if m:
                return m.group(1)
    protocolo = row.get("Protocolo") or row.get("Registro") or ""
    # UF-F-IBGE-COBRADE-YYYYMMDD
    parts = protocolo.split("-")
    for p in parts:
        if p.isdigit() and len(p) == 5:
            return p
    return None


def _is_flood_cobrade(code: str | None) -> bool:
    if not code:
        return False
    return any(code.startswith(p[:5]) or code.startswith(p) for p in FLOOD_COBRADE_PREFIXES) or code[:3] in {
        "121",
        "122",
        "123",
    }


def _tipo_from_cobrade(code: str) -> str:
    return TIPO_BY_PREFIX.get(code[:3], "Inundação")


def iter_flood_events_from_csv(
    path: Path,
    *,
    ibge_filter: Iterable[str] | None = None,
) -> list[dict[str, Any]]:
    allowed = {str(c).zfill(7)[:7] for c in (ibge_filter or [])} if ibge_filter is not None else None
    text = _decode_csv_text(path.read_bytes())
    lines = text.splitlines()
    header_idx = _find_header_line(lines)
    body = "\n".join(lines[header_idx:])
    reader = csv.DictReader(io.StringIO(body), delimiter=";")
    if reader.fieldnames and len(reader.fieldnames) < 3:
        reader = csv.DictReader(io.StringIO(body), delimiter=",")

    events: list[dict[str, Any]] = []
    for row in reader:
        if not row:
            continue
        # normaliza chaves
        clean = {(k or "").strip(): (v or "").strip() for k, v in row.items() if k}
        ibge = _ibge_from_row(clean)
        if not ibge:
            continue
        if allowed is not None and ibge not in allowed:
            continue
        cobrade = _cobrade_code(clean)
        if not _is_flood_cobrade(cobrade):
            continue
        data = None
        for key in ("Data", "Data do Registro", "Data Ocorrência", "Data Ocorrencia", "DATA"):
            if key in clean:
                data = _parse_date(clean[key])
                if data:
                    break
        if data is None:
            protocolo = clean.get("Protocolo") or clean.get("Registro") or ""
            m = re.search(r"(20\d{6})$", protocolo.replace("-", ""))
            if m:
                data = _parse_date(m.group(1))
        if data is None:
            continue

        afetados = 0
        for key in ("Total de Afetados", "Afetados", "População Afetada", "DH_total"):
            if key in clean and clean[key]:
                try:
                    afetados = int(float(clean[key].replace(".", "").replace(",", ".")))
                except ValueError:
                    afetados = 0
                break

        events.append({
            "codigo_ibge": ibge,
            "data": data,
            "tipo": _tipo_from_cobrade(cobrade or "12100"),
            "cobrade": cobrade,
            "afetados": afetados,
            "protocolo": clean.get("Protocolo") or clean.get("Registro") or "",
            "municipio_nome": clean.get("Município") or clean.get("Municipio") or "",
            "referencia": f"S2ID/SEDEC CSV — {cobrade} — {clean.get('Protocolo') or clean.get('Registro') or data.isoformat()}",
        })
    return events


def ingest_national_s2id_for_pilotos(
    db: Session,
    *,
    years: list[int] | None = None,
    codigo_ibge_list: list[str] | None = None,
    force_download: bool = False,
) -> dict[str, Any]:
    """Baixa CSVs MIDR e upserta eventos hidrológicos oficiais nos municípios-piloto."""
    targets = [str(c).zfill(7)[:7] for c in (codigo_ibge_list or ML_TARGET_IBGE_CODES)]
    resources = list_ckan_csv_resources()
    if years:
        year_set = set(years)
        resources = [r for r in resources if r.get("year") in year_set]

    created = 0
    skipped = 0
    by_muni: dict[str, int] = {c: 0 for c in targets}
    files_used: list[str] = []

    muni_by_code = {
        m.codigo_ibge: m
        for m in db.query(Municipio).filter(Municipio.codigo_ibge.in_(targets)).all()
    }

    # Preferir CSVs locais válidos (download MDR costuma cair em WAF)
    local_csvs = sorted(
        p for p in _downloads_dir().glob("s2id_*.csv") if _looks_like_csv(p.read_bytes()[:800])
    )
    if years and local_csvs:
        year_set = set(years)
        local_csvs = [p for p in local_csvs if _year_from_name(p.name) in year_set]

    paths_to_parse: list[Path] = list(local_csvs)
    if not paths_to_parse or force_download:
        for res in resources:
            url = res.get("url")
            if not url:
                continue
            try:
                path = download_csv(url, force=force_download)
                if path not in paths_to_parse:
                    paths_to_parse.append(path)
            except Exception as exc:
                logger.warning("Falha download S2ID %s: %s", url, exc)
                continue

    if not paths_to_parse:
        return {
            "ok": False,
            "created": 0,
            "skipped": 0,
            "by_municipio": by_muni,
            "files": [],
            "resources_seen": len(resources),
            "reason": "csv_indisponivel_waf",
            "nota": (
                f"O portal MDR rejeitou o download automático. "
                f"Salve os CSVs anuais em {_downloads_dir()} como s2id_YYYY.csv "
                f"(página: https://dadosabertos.mdr.gov.br/dataset/s2id_sedec) e rode de novo."
            ),
            "fonte": "dadosabertos.mdr.gov.br/dataset/s2id_sedec",
        }

    for path in paths_to_parse:
        files_used.append(path.name)
        events = iter_flood_events_from_csv(path, ibge_filter=targets)
        for ev in events:
            muni = muni_by_code.get(ev["codigo_ibge"])
            if not muni:
                continue
            exists = (
                db.query(HistoricoDesastreS2ID)
                .filter(
                    HistoricoDesastreS2ID.municipio_id == muni.id,
                    HistoricoDesastreS2ID.data_ocorrencia == ev["data"],
                    HistoricoDesastreS2ID.tipo_desastre == ev["tipo"],
                    HistoricoDesastreS2ID.referencia == ev["referencia"],
                )
                .first()
            )
            if exists:
                skipped += 1
                continue
            # Evita duplicar curados na mesma data/tipo
            exists2 = (
                db.query(HistoricoDesastreS2ID)
                .filter(
                    HistoricoDesastreS2ID.municipio_id == muni.id,
                    HistoricoDesastreS2ID.data_ocorrencia == ev["data"],
                    HistoricoDesastreS2ID.tipo_desastre == ev["tipo"],
                    HistoricoDesastreS2ID.data_quality.in_(("oficial", "oficial_curado")),
                )
                .first()
            )
            if exists2:
                skipped += 1
                continue

            geom = None
            try:
                from sqlalchemy import func

                # ST_PointOnSurface evita ponto fora do polígono em multipolígonos
                pt = db.scalar(func.ST_PointOnSurface(muni.geom))
                if pt is not None:
                    geom = pt
            except Exception:
                geom = None

            db.add(
                HistoricoDesastreS2ID(
                    municipio_id=muni.id,
                    tipo_desastre=ev["tipo"],
                    data_ocorrencia=ev["data"],
                    populacao_afetada=int(ev["afetados"] or 0),
                    danos_materiais=0,
                    data_quality="oficial",
                    fonte="s2id_nacional_mdr",
                    referencia=ev["referencia"][:255],
                    geom=geom,
                )
            )
            created += 1
            by_muni[ev["codigo_ibge"]] = by_muni.get(ev["codigo_ibge"], 0) + 1

    if created:
        db.commit()
        try:
            from app.services.evento_alagamento_service import sync_official_s2id_to_observed_events

            for code in targets:
                sync_official_s2id_to_observed_events(db, code)
        except Exception as exc:
            logger.warning("sync evento_alagamento após S2ID nacional: %s", exc)

    return {
        "ok": True,
        "created": created,
        "skipped": skipped,
        "by_municipio": by_muni,
        "files": files_used,
        "resources_seen": len(resources),
        "fonte": "dadosabertos.mdr.gov.br/dataset/s2id_sedec",
    }
