from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any, Dict, List

from sqlalchemy.orm import Session

from app.data_connectors.capag_collector import collect_capag_municipality
from app.data_connectors.constants import TARGET_IBGE_CODES
from app.data_connectors.ibge_collector import collect_ibge_municipality
from app.data_connectors.siconfi_collector import collect_siconfi_municipality
from app.data_connectors.snis_sinisa_collector import collect_snis_municipality
from app.data_connectors.external_sources_collector import sync_external_sources_batch
from app.data_connectors.singedlab_rs_collector import sync_singedlab_batch
from app.models import IntegrationRun, Municipio, MunicipioFiscal, MunicipioFonteExterna, MunicipioIbge, MunicipioSaneamento


class IntegrationOrchestrator:
    def __init__(self, db: Session):
        self.db = db

    def sync_all(self, codigos: List[str] | None = None) -> Dict[str, Any]:
        targets = codigos or TARGET_IBGE_CODES
        summary = {"ibge": 0, "siconfi": 0, "capag": 0, "snis": 0, "fontes_externas": 0, "singedlab": 0, "errors": []}

        for codigo in targets:
            try:
                if self._sync_ibge(codigo):
                    summary["ibge"] += 1
            except Exception as exc:
                summary["errors"].append({"source": "ibge", "codigo_ibge": codigo, "error": str(exc)})
                self._register_run("ibge", "FALHA", 0, str(exc))

            try:
                if self._sync_siconfi(codigo):
                    summary["siconfi"] += 1
            except Exception as exc:
                summary["errors"].append({"source": "siconfi", "codigo_ibge": codigo, "error": str(exc)})
                self._register_run("siconfi", "FALHA", 0, str(exc))

            try:
                capag = collect_capag_municipality(codigo)
                self._upsert_fiscal_capag(codigo, capag)
                summary["capag"] += 1
            except Exception as exc:
                summary["errors"].append({"source": "capag", "codigo_ibge": codigo, "error": str(exc)})
                self._register_run("capag", "FALHA", 0, str(exc))

            try:
                if self._sync_snis(codigo):
                    summary["snis"] += 1
            except Exception as exc:
                summary["errors"].append({"source": "snis", "codigo_ibge": codigo, "error": str(exc)})
                self._register_run("snis", "FALHA", 0, str(exc))

        try:
            ext = sync_external_sources_batch(self.db, targets)
            summary["fontes_externas"] = ext.get("processed", 0)
            if ext.get("errors"):
                summary["errors"].extend(
                    [{"source": "fontes_externas", **err} for err in ext["errors"][:20]]
                )
        except Exception as exc:
            summary["errors"].append({"source": "fontes_externas", "error": str(exc)})
            self._register_run("fontes_externas", "FALHA", 0, str(exc))

        try:
            sl = sync_singedlab_batch(self.db, targets)
            summary["singedlab"] = sl.get("processed", 0)
            if sl.get("errors"):
                summary["errors"].extend(
                    [{"source": "singedlab", **err} for err in sl["errors"][:20]]
                )
        except Exception as exc:
            summary["errors"].append({"source": "singedlab", "error": str(exc)})
            self._register_run("singedlab", "FALHA", 0, str(exc))

        self._register_run("ibge", "OK", summary["ibge"])
        self._register_run("siconfi", "OK", summary["siconfi"])
        self._register_run("capag", "OK", summary["capag"])
        self._register_run("snis", "OK", summary["snis"])
        self._register_run("fontes_externas", "OK", summary["fontes_externas"])
        self._register_run("singedlab", "OK", summary["singedlab"])
        self.db.commit()

        from app.observability.metrics import record_integration_sync

        for source in ("ibge", "siconfi", "capag", "snis", "fontes_externas", "singedlab"):
            record_integration_sync(source, True, summary.get(source, 0))
        return summary

    def _municipio_id(self, codigo_ibge: str) -> int | None:
        muni = self.db.query(Municipio).filter(Municipio.codigo_ibge == codigo_ibge).first()
        return muni.id if muni else None

    def _sync_ibge(self, codigo_ibge: str) -> bool:
        payload = collect_ibge_municipality(codigo_ibge)
        if not payload.get("populacao"):
            return False

        row = self.db.query(MunicipioIbge).filter(MunicipioIbge.codigo_ibge == codigo_ibge).first()
        if not row:
            row = MunicipioIbge(codigo_ibge=codigo_ibge)
            self.db.add(row)

        row.municipio_id = self._municipio_id(codigo_ibge)
        row.populacao = payload["populacao"]
        row.populacao_ano = payload.get("populacao_ano")
        row.area_km2 = payload.get("area_km2")
        row.area_ano = payload.get("area_ano")
        row.pib_per_capita = payload.get("pib_per_capita")
        row.pib_ano = payload.get("pib_ano")
        row.pib_total_mil_reais = payload.get("pib_total_mil_reais")
        row.pib_serie = payload.get("pib_serie") or []
        row.idh = payload.get("idh")
        row.idh_ano = payload.get("idh_ano")
        row.densidade_demografica = payload.get("densidade_demografica")
        row.data_quality = payload.get("data_quality", "oficial")
        row.fonte = payload.get("fonte")
        row.atualizado_em = payload.get("atualizado_em")
        row.raw_payload = json.dumps(payload.get("raw_payload") or {}, ensure_ascii=False)

        muni = self.db.query(Municipio).filter(Municipio.codigo_ibge == codigo_ibge).first()
        if muni:
            muni.populacao = payload["populacao"]
            if payload.get("area_km2"):
                muni.area_km2 = payload["area_km2"]
        return True

    def _sync_siconfi(self, codigo_ibge: str) -> bool:
        payload = collect_siconfi_municipality(codigo_ibge)
        if not any(payload.get(field) is not None for field in (
            "receita_corrente_liquida", "despesa_pessoal_pct_rcl", "resultado_primario"
        )):
            return False

        row = self.db.query(MunicipioFiscal).filter(MunicipioFiscal.codigo_ibge == codigo_ibge).first()
        if not row:
            row = MunicipioFiscal(codigo_ibge=codigo_ibge)
            self.db.add(row)

        row.municipio_id = self._municipio_id(codigo_ibge)
        row.receita_corrente_liquida = payload.get("receita_corrente_liquida")
        row.despesa_pessoal_pct_rcl = payload.get("despesa_pessoal_pct_rcl")
        row.divida_consolidada = payload.get("divida_consolidada")
        row.resultado_primario = payload.get("resultado_primario")
        row.exec_saude = payload.get("exec_saude")
        row.exec_habitacao = payload.get("exec_habitacao")
        row.exec_saneamento = payload.get("exec_saneamento")
        row.exec_meio_ambiente = payload.get("exec_meio_ambiente")
        row.exec_defesa_civil = payload.get("exec_defesa_civil")
        row.exercicio = payload.get("exercicio")
        row.periodo = payload.get("periodo")
        row.data_quality = payload.get("data_quality", "oficial")
        row.fonte = payload.get("fonte")
        row.atualizado_em = payload.get("atualizado_em")
        row.raw_payload = json.dumps(payload.get("raw_payload") or {}, ensure_ascii=False)
        return True

    def _sync_snis(self, codigo_ibge: str) -> bool:
        payload = collect_snis_municipality(codigo_ibge)
        if payload.get("data_quality") == "lacuna":
            return False

        row = self.db.query(MunicipioSaneamento).filter(MunicipioSaneamento.codigo_ibge == codigo_ibge).first()
        if not row:
            row = MunicipioSaneamento(codigo_ibge=codigo_ibge)
            self.db.add(row)

        row.municipio_id = self._municipio_id(codigo_ibge)
        row.cobertura_agua_pct = payload.get("cobertura_agua_pct")
        row.cobertura_esgoto_pct = payload.get("cobertura_esgoto_pct")
        row.indice_perdas_agua_pct = payload.get("indice_perdas_agua_pct")
        row.indice_atendimento_esgoto_pct = payload.get("indice_atendimento_esgoto_pct")
        row.indice_drenagem = payload.get("indice_drenagem")
        row.ano_referencia = payload.get("ano_referencia")
        row.data_quality = payload.get("data_quality", "oficial")
        row.fonte = payload.get("fonte")
        row.atualizado_em = payload.get("atualizado_em")
        row.raw_payload = json.dumps(payload.get("raw_payload") or {}, ensure_ascii=False)
        return True

    def _upsert_fiscal_capag(self, codigo_ibge: str, capag: Dict[str, Any]) -> None:
        row = self.db.query(MunicipioFiscal).filter(MunicipioFiscal.codigo_ibge == codigo_ibge).first()
        if not row:
            row = MunicipioFiscal(codigo_ibge=codigo_ibge, municipio_id=self._municipio_id(codigo_ibge))
            self.db.add(row)
        row.nota_capag = capag.get("nota_capag")
        if capag.get("nota_capag"):
            row.data_quality = "oficial"
            row.fonte = capag.get("fonte")
            row.atualizado_em = capag.get("atualizado_em")
        row.raw_payload = json.dumps(
            {
                "nota_capag_raw": capag.get("nota_capag_raw"),
                "indicadores": capag.get("indicadores") or [],
                "origem_nota": capag.get("origem_nota"),
            },
            ensure_ascii=False,
        )

    def _register_run(self, source: str, status: str, records_count: int, error_message: str | None = None) -> None:
        self.db.add(IntegrationRun(
            source=source,
            status=status,
            records_count=records_count,
            last_success_at=datetime.now(timezone.utc) if status == "OK" else None,
            error_message=error_message,
        ))

    def status(self) -> List[Dict[str, Any]]:
        sources = ("ibge", "siconfi", "capag", "snis", "fontes_externas")
        output = []
        for source in sources:
            latest = (
                self.db.query(IntegrationRun)
                .filter(IntegrationRun.source == source)
                .order_by(IntegrationRun.id.desc())
                .first()
            )
            if source == "ibge":
                records = self.db.query(MunicipioIbge).count()
            elif source == "snis":
                records = self.db.query(MunicipioSaneamento).count()
            elif source == "fontes_externas":
                records = self.db.query(MunicipioFonteExterna).count()
            else:
                records = self.db.query(MunicipioFiscal).count()

            last_at = latest.last_success_at if latest else None
            status = latest.status if latest else "DESATUALIZADO"
            if records == 0:
                status = "DESATUALIZADO"
            output.append({
                "source": source,
                "status": status,
                "records_count": records,
                "last_success_at": last_at.isoformat() if last_at else None,
                "error_message": latest.error_message if latest else None,
            })
        return output
