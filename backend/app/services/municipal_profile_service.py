"""Perfil do município (17h.4a) — porte, CAPAG, Plano Diretor e proxy de Defesa Civil.

Condiciona recomendações e o catálogo de medidas à realidade fiscal/institucional.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.models import Municipio, MunicipioFiscal
from app.services.casos_sucesso_service import POP_FAIXAS
from app.services.maturity_engine import compute_maturity
from app.services.mitigation_planner import PLAN_DIRECTOR_SOURCES
from app.services.report_generator import _ensure_capag_fresh

PORTE_LABEL = {
    "pequeno": "Pequeno",
    "medio": "Médio",
    "grande": "Grande",
    "metropole": "Metrópole",
}

CAPAG_INTERPRETACAO = {
    "A": "Capacidade de pagamento robusta — crédito com garantia da União sem restrições adicionais.",
    "B": "Capacidade adequada — crédito com garantia da União, com monitoramento.",
    "C": "Atenção — restrições para garantia da União; priorizar não reembolsável.",
    "D": "Capacidade limitada — alto risco fiscal; foco em prevenção e apoio técnico.",
    "E": "Situação crítica — evitar operações de crédito; medidas de baixo custo.",
}


def classify_porte(populacao: int | None) -> str:
    """Classifica porte populacional (mesmas faixas dos casos de sucesso)."""
    pop = int(populacao or 0)
    for faixa, (lo, hi) in POP_FAIXAS.items():
        if lo <= pop < hi:
            return faixa
    return "metropole" if pop >= 1_000_000 else "pequeno"


def build_municipal_profile(
    db: Session,
    codigo_ibge: str,
    *,
    maturity: dict[str, Any] | None = None,
) -> dict[str, Any]:
    code = str(codigo_ibge).zfill(7)[:7]
    muni = db.query(Municipio).filter(Municipio.codigo_ibge == code).first()
    if not muni:
        raise ValueError(f"Município {code} não encontrado")

    pop = int(muni.populacao or 0)
    porte = classify_porte(pop)

    fiscal, capag_meta = _ensure_capag_fresh(db, muni)
    nota_raw = (capag_meta.get("nota") or (fiscal.nota_capag if fiscal else None) or "")
    nota = str(nota_raw).upper()[:1] or None
    if nota and nota not in CAPAG_INTERPRETACAO:
        nota = None

    if fiscal is None:
        fiscal = db.query(MunicipioFiscal).filter(MunicipioFiscal.codigo_ibge == code).first()
    exec_dc = float(fiscal.exec_defesa_civil) if fiscal and fiscal.exec_defesa_civil is not None else None

    pd_sources = PLAN_DIRECTOR_SOURCES.get(code) or []
    maturity_data = maturity if maturity is not None else compute_maturity(db, code)
    pd_fonte = next((f for f in maturity_data.get("fontes") or [] if f.get("id") == "plano_diretor"), None)
    pd_status = (pd_fonte or {}).get("status") or ("OFICIAL" if pd_sources else "LACUNA")

    defesa = {
        "sinal": "presente" if exec_dc and exec_dc > 0 else ("ausente" if exec_dc == 0 else "desconhecido"),
        "execucao_siconfi": exec_dc,
        "proxy": "Gasto em Defesa Civil (SICONFI) — não confirma existência de órgão municipal",
        "tem_gasto_registrado": bool(exec_dc and exec_dc > 0),
    }

    restricoes: list[str] = []
    if nota in {"C", "D", "E"}:
        restricoes.append(
            f"CAPAG {nota}: priorizar medidas de baixo/médio custo e fontes não reembolsáveis."
        )
    if porte == "pequeno":
        restricoes.append(
            "Município de porte pequeno — preferir ações operacionais e de baixo custo antes de obras estruturais."
        )
    if pd_status == "LACUNA":
        restricoes.append(
            "Plano Diretor sem fonte cadastrada — alinhar intervenções à legislação urbanística local."
        )
    if defesa["sinal"] != "presente":
        restricoes.append(
            "Sem evidência de gasto em Defesa Civil no SICONFI — reforçar articulação e protocolo municipal."
        )

    return {
        "codigo_ibge": code,
        "nome": muni.nome,
        "uf": muni.uf,
        "populacao": pop,
        "porte": porte,
        "porte_label": PORTE_LABEL.get(porte, porte),
        "capag": {
            "nota": nota,
            "status": capag_meta.get("status"),
            "interpretacao": CAPAG_INTERPRETACAO.get(nota or "", "Nota CAPAG não disponível."),
            "indicadores": capag_meta.get("indicadores") or [],
        },
        "plano_diretor": {
            "status": pd_status,
            "fontes_cadastradas": len(pd_sources),
            "titulos": [s.get("titulo") for s in pd_sources[:3] if isinstance(s, dict)],
        },
        "defesa_civil": defesa,
        "restricoes": restricoes,
        "maturidade_tier": maturity_data.get("classificacao"),
        "maturidade_score": maturity_data.get("score"),
    }
