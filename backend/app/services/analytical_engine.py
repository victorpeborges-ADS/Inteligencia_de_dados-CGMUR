import json
import logging
from collections import OrderedDict
from sqlalchemy.orm import Session
from sqlalchemy import func
from app.models import Municipio, Bairro, SetorCensitario, CoberturaVegetalMapBiomas, HistoricoDesastreS2ID, AlertaCemaden, InfraestruturaUrbana, MunicipioSaude, MunicipioSeguranca, MunicipioFiscal, EstabelecimentoSaude
from shapely.geometry import shape, mapping
from shapely.ops import unary_union
from typing import List, Dict, Any

logger = logging.getLogger(__name__)

class AnalyticalEngine:
    # Nota (jul/2026): _covered_area_deg é chamado uma vez por bairro/setor (centenas de
    # vezes por request) sempre com a MESMA lista de cover_geoms (ex.: todos os polígonos
    # "Área Urbana" do MapBiomas do município). Sem memoização, o unary_union + make_valid
    # dessa lista era refeito do zero em cada iteração — em Recife isso sozinho custava
    # ~84s no painel de risco. A chave usa id()+len() da lista (mesmo objeto Python
    # reaproveitado dentro do laço do caller) com um LRU pequeno, evitando qualquer
    # crescimento de memória sem limite entre requests.
    _cover_union_cache: "OrderedDict[tuple[int, int], Any]" = OrderedDict()
    _COVER_CACHE_MAXSIZE = 32

    @staticmethod
    def _shape_from_db_geometry(db: Session, geom) -> Any:
        return shape(json.loads(db.scalar(geom.ST_AsGeoJSON())))

    @staticmethod
    def _repair_shape(geom: Any) -> Any:
        if geom is None or geom.is_empty:
            return geom
        if geom.is_valid:
            return geom
        try:
            from shapely.validation import make_valid

            return make_valid(geom)
        except Exception:
            return geom.buffer(0)

    @staticmethod
    def _safe_unary_union(shapes: list[Any]) -> Any | None:
        fixed = [
            AnalyticalEngine._repair_shape(s)
            for s in shapes
            if s is not None and not s.is_empty
        ]
        if not fixed:
            return None
        try:
            return unary_union(fixed)
        except Exception as exc:
            logger.debug("unary_union falhou, tentando buffer(0): %s", exc)
            try:
                return unary_union([s.buffer(0) for s in fixed])
            except Exception:
                return None

    @staticmethod
    def _merged_cover_shape(db: Session, cover_geoms) -> Any | None:
        if not cover_geoms:
            return None
        cache = AnalyticalEngine._cover_union_cache
        key = (id(cover_geoms), len(cover_geoms))
        cached = cache.get(key)
        if cached is not None:
            cache.move_to_end(key)
            return cached

        cover_shapes = [
            AnalyticalEngine._shape_from_db_geometry(db, row.geom)
            for row in cover_geoms
        ]
        merged = AnalyticalEngine._safe_unary_union(cover_shapes) if cover_shapes else None
        cache[key] = merged
        cache.move_to_end(key)
        while len(cache) > AnalyticalEngine._COVER_CACHE_MAXSIZE:
            cache.popitem(last=False)
        return merged

    @staticmethod
    def _covered_area_deg(db: Session, base_geom, cover_geoms) -> float:
        base_shape = AnalyticalEngine._repair_shape(
            AnalyticalEngine._shape_from_db_geometry(db, base_geom),
        )
        merged = AnalyticalEngine._merged_cover_shape(db, cover_geoms)
        if merged is None:
            return 0.0
        try:
            return float(base_shape.intersection(merged).area)
        except Exception as exc:
            logger.debug("intersection cobertura falhou: %s", exc)
            return 0.0

    @staticmethod
    def _percentile_ranks(values: list[float]) -> list[float]:
        """Rank percentual 0–1 dentro do município (empates → média dos ranks)."""
        n = len(values)
        if n == 0:
            return []
        if n == 1:
            return [0.5]
        indexed = sorted(enumerate(values), key=lambda t: t[1])
        ranks = [0.0] * n
        i = 0
        while i < n:
            j = i
            while j + 1 < n and indexed[j + 1][1] == indexed[i][1]:
                j += 1
            avg_rank = (i + j) / 2.0
            pct = avg_rank / (n - 1)
            for k in range(i, j + 1):
                ranks[indexed[k][0]] = pct
            i = j + 1
        return ranks

    @staticmethod
    def _bairro_area_km2(db: Session, geom) -> float:
        """Área aproximada em km² (SRID 4326 → fator tropical ~Recife)."""
        area_deg = db.scalar(func.ST_Area(geom))
        if area_deg is None or float(area_deg) <= 0:
            return 0.01
        # 1°² ≈ 12_100–12_300 km² perto de lat -8°
        return float(area_deg) * 12300.0

    @staticmethod
    def _resolve_bairro_renda(db: Session, muni: Municipio, bairro: Bairro) -> tuple[float, str]:
        """Renda mensal do bairro — prioriza tabela local conhecida; evita setores flat."""
        from app.services.socioeconomic_engine import RECIFE_BAIRRO_RENDA

        nome = (bairro.nome or "").strip()
        if nome in RECIFE_BAIRRO_RENDA:
            return float(RECIFE_BAIRRO_RENDA[nome]), "recife_bairro_renda"
        # match case-insensitive / parcial
        for key, val in RECIFE_BAIRRO_RENDA.items():
            if key.casefold() == nome.casefold() or key.casefold() in nome.casefold() or nome.casefold() in key.casefold():
                return float(val), "recife_bairro_renda"

        if bairro.renda_media_censo2022 is not None and float(bairro.renda_media_censo2022) > 0:
            return float(bairro.renda_media_censo2022), "bairro_renda_censo"

        # setores cujo centróide cai no bairro (evita overcount por ST_Intersects amplo)
        sectors = (
            db.query(SetorCensitario)
            .filter(
                SetorCensitario.municipio_id == muni.id,
                func.ST_Contains(bairro.geom, func.ST_Centroid(SetorCensitario.geom)),
            )
            .all()
        )
        if sectors:
            avg = sum(float(s.renda_media or 0) for s in sectors) / len(sectors)
            if avg > 0:
                return avg, "setor_centroid"

        return 1800.0, "fallback"

    @staticmethod
    def calculate_climate_vulnerability(db: Session, municipio_id: int) -> List[Dict[str, Any]]:
        """
        IVC por bairro — sensibilidade relativa ao município + exposição territorial.

        Correção (jul/2026): a fórmula antiga saturava densidade (pop inflada / teto 15k)
        e usava renda de setores quase constante → IVC ~igual em todos os bairros.
        Agora: renda prioritária por bairro, densidade por área share do município,
        scores por percentil intra-municipal e exposição com impermeabilização MapBiomas.
        """
        muni = db.query(Municipio).filter(Municipio.id == municipio_id).first()
        if not muni:
            return []

        bairros = db.query(Bairro).filter(Bairro.municipio_id == municipio_id).all()
        if not bairros:
            return []

        muni_area = AnalyticalEngine._bairro_area_km2(db, muni.geom)
        muni_pop = int(muni.populacao or 0) or 1

        urban_cover = db.query(CoberturaVegetalMapBiomas).filter(
            CoberturaVegetalMapBiomas.municipio_id == municipio_id,
            CoberturaVegetalMapBiomas.classe_uso == "Área Urbana",
        ).all()
        forest_cover = db.query(CoberturaVegetalMapBiomas).filter(
            CoberturaVegetalMapBiomas.municipio_id == municipio_id,
            CoberturaVegetalMapBiomas.classe_uso == "Vegetação / Floresta",
        ).all()

        raw_rows: list[dict[str, Any]] = []
        densities: list[float] = []
        incomes: list[float] = []

        for b in bairros:
            area_km2 = max(AnalyticalEngine._bairro_area_km2(db, b.geom), 0.01)
            # População: se a soma dos pop_censo está inflada, redistribui pop municipal por área
            pop_raw = int(b.pop_censo2022) if b.pop_censo2022 is not None else None
            pop_est = int(round(muni_pop * (area_km2 / muni_area))) if muni_area > 0 else (pop_raw or 0)
            pop = pop_est if (pop_raw is None or pop_raw <= 0) else pop_raw

            avg_income, renda_fonte = AnalyticalEngine._resolve_bairro_renda(db, muni, b)
            density = pop / area_km2 if area_km2 > 0 else 0.0

            disasters_count = db.query(HistoricoDesastreS2ID).filter(
                HistoricoDesastreS2ID.municipio_id == municipio_id,
                func.ST_Intersects(b.geom, HistoricoDesastreS2ID.geom),
            ).count()
            active_alerts = db.query(AlertaCemaden).filter(
                AlertaCemaden.municipio_id == municipio_id,
                func.ST_Intersects(b.geom, AlertaCemaden.geom),
            ).all()
            alert_weight = 0.0
            for alt in active_alerts:
                nivel = str(getattr(alt, "nivel_alerta", "") or "").upper()
                if nivel in {"MUITO_ALTO", "VERMELHO"}:
                    alert_weight = max(alert_weight, 1.0)
                elif nivel in {"ALTO", "LARANJA"}:
                    alert_weight = max(alert_weight, 0.8)
                elif nivel in {"MEDIO", "MÉDIO", "AMARELO"}:
                    alert_weight = max(alert_weight, 0.5)
                elif nivel in {"BAIXO", "VERDE"}:
                    alert_weight = max(alert_weight, 0.2)

            area_deg = db.scalar(func.ST_Area(b.geom)) or 0.0
            urban_area_deg = AnalyticalEngine._covered_area_deg(db, b.geom, urban_cover)
            urban_pct = float(urban_area_deg) / float(area_deg) if area_deg else 0.5
            veg_area_deg = AnalyticalEngine._covered_area_deg(db, b.geom, forest_cover)
            veg_pct = float(veg_area_deg) / float(area_deg) if area_deg else 0.0

            hospitals_count = db.query(InfraestruturaUrbana).filter(
                InfraestruturaUrbana.tipo == "hospital",
                func.ST_Intersects(b.geom, InfraestruturaUrbana.geom),
            ).count()

            densities.append(float(density))
            incomes.append(float(avg_income))
            raw_rows.append({
                "b": b,
                "area_km2": area_km2,
                "populacao": pop,
                "pop_raw": pop_raw,
                "pop_est_area": pop_est,
                "renda_media": avg_income,
                "renda_fonte": renda_fonte,
                "density": density,
                "disasters_count": int(disasters_count),
                "alert_weight": alert_weight,
                "urban_pct": urban_pct,
                "veg_pct": veg_pct,
                "hospitais_count": int(hospitals_count),
            })

        # Se pop_censo somada >> pop municipal, troca para estimativa por área (evita densidade tetada)
        pop_sum = sum(int(r["pop_raw"] or 0) for r in raw_rows)
        use_area_pop = pop_sum > muni_pop * 1.35
        if use_area_pop:
            densities = []
            for r in raw_rows:
                r["populacao"] = int(r["pop_est_area"])
                r["density"] = r["populacao"] / r["area_km2"] if r["area_km2"] > 0 else 0.0
                densities.append(float(r["density"]))

        density_ranks = AnalyticalEngine._percentile_ranks(densities)
        # renda alta → sensibilidade baixa
        income_ranks = AnalyticalEngine._percentile_ranks(incomes)
        income_sensitivity = [1.0 - r for r in income_ranks]

        results: list[dict[str, Any]] = []
        for idx, r in enumerate(raw_rows):
            density_score = density_ranks[idx]
            income_score = income_sensitivity[idx]
            sensibilidade = (density_score * 0.55) + (income_score * 0.45)

            disaster_score = min(r["disasters_count"] / 5.0, 1.0)
            impermeabilizacao = min(float(r["urban_pct"]), 1.0)
            # Exposição: histórico + alerta + tecido urbano (evita coluna zero quando S2ID é pontual)
            exposicao = (
                disaster_score * 0.35
                + float(r["alert_weight"]) * 0.25
                + impermeabilizacao * 0.40
            )

            veg_score = min(float(r["veg_pct"]) * 3.0, 1.0)
            infra_score = min(r["hospitais_count"] / 2.0, 1.0)
            capacidade_adaptacao = (veg_score * 0.6) + (infra_score * 0.4)

            ivc = (exposicao + sensibilidade) / 2.0
            ivc = ivc * (1.0 - (capacidade_adaptacao * 0.3))
            ivc = round(max(0.0, min(1.0, ivc)), 2)

            b = r["b"]
            results.append({
                "id": b.id,
                "bairro_nome": b.nome,
                "exposicao": round(exposicao, 2),
                "sensibilidade": round(sensibilidade, 2),
                "capacidade_adaptacao": round(capacidade_adaptacao, 2),
                "indice_vulnerabilidade": ivc,
                "populacao": int(r["populacao"]),
                "densidade_hab_km2": round(float(r["density"]), 1),
                "renda_media": round(float(r["renda_media"]), 2),
                "renda_fonte": r["renda_fonte"],
                "density_score": round(density_score, 3),
                "income_score": round(income_score, 3),
                "s2id_desastres_count": int(r["disasters_count"]),
                "alertas_peso": round(float(r["alert_weight"]), 2),
                "veg_pct": round(float(r["veg_pct"]), 3),
                "urban_pct": round(float(r["urban_pct"]), 3),
                "hospitais_count": int(r["hospitais_count"]),
                "pop_method": "area_share" if use_area_pop else "bairro_censo",
                "nota_metodologica": (
                    "IVC relativo ao município (percentis de densidade/renda). "
                    "Não é índice oficial IBGE/CEMADEN."
                ),
            })

        return results

    @staticmethod
    def _water_proximity_score(db: Session, geom, water_rows: list, muni_shape) -> float:
        """Score contínuo 0.2–1.0 pela distância ao corpo d'água (evita faixa binária)."""
        if not water_rows:
            return 0.25
        unit = AnalyticalEngine._repair_shape(AnalyticalEngine._shape_from_db_geometry(db, geom))
        water_shapes = [AnalyticalEngine._shape_from_db_geometry(db, row.geom) for row in water_rows]
        rivers = AnalyticalEngine._safe_unary_union(water_shapes)
        if rivers is None:
            return 0.25
        if unit.intersects(rivers):
            return 1.0
        minx, miny, maxx, maxy = muni_shape.bounds
        max_ref = max(((maxx - minx) ** 2 + (maxy - miny) ** 2) ** 0.5 * 0.4, 0.004)
        dist = unit.centroid.distance(rivers)
        return round(max(0.2, min(1.0, 1.0 - dist / max_ref)), 2)

    @staticmethod
    def _intersects_shape(db: Session, unit_geom, feature_geom) -> bool:
        try:
            unit = AnalyticalEngine._repair_shape(
                AnalyticalEngine._shape_from_db_geometry(db, unit_geom),
            )
            feat = AnalyticalEngine._repair_shape(
                AnalyticalEngine._shape_from_db_geometry(db, feature_geom),
            )
            return bool(unit.intersects(feat))
        except Exception as exc:
            logger.debug("intersects_shape falhou: %s", exc)
            return False

    @staticmethod
    def _iri_for_unit(
        db: Session,
        municipio_id: int,
        geom,
        muni_shape,
        water_rows: list,
        *,
        flood_events: list | None = None,
        urban_cover: list | None = None,
    ) -> dict[str, float]:
        if flood_events is None:
            flood_events = db.query(HistoricoDesastreS2ID).filter(
                HistoricoDesastreS2ID.municipio_id == municipio_id,
                HistoricoDesastreS2ID.tipo_desastre.in_(["Inundação", "Alagamento Urbano"]),
            ).all()
        flood_disasters = sum(
            1 for ev in flood_events if AnalyticalEngine._intersects_shape(db, geom, ev.geom)
        )
        s2id_score = min(flood_disasters / 3.0, 1.0)

        area_deg = db.scalar(func.ST_Area(geom))
        if urban_cover is None:
            urban_cover = db.query(CoberturaVegetalMapBiomas).filter(
                CoberturaVegetalMapBiomas.municipio_id == municipio_id,
                CoberturaVegetalMapBiomas.classe_uso == "Área Urbana",
            ).all()
        urban_area_deg = AnalyticalEngine._covered_area_deg(db, geom, urban_cover)
        urban_pct = float(urban_area_deg) / float(area_deg) if urban_area_deg and area_deg else 0.5
        impermeabilizacao_score = min(urban_pct, 1.0)

        water_score = AnalyticalEngine._water_proximity_score(db, geom, water_rows, muni_shape)
        iri = (s2id_score * 0.4) + (impermeabilizacao_score * 0.4) + (water_score * 0.2)
        iri = round(max(0.0, min(1.0, iri)), 2)
        return {
            "s2id_historico_score": round(s2id_score, 2),
            "impermeabilizacao_score": round(impermeabilizacao_score, 2),
            "hidrografia_proximidade_score": water_score,
            "indice_risco_inundacao": iri,
        }

    @staticmethod
    def calculate_flood_risk_setores(db: Session, municipio_id: int) -> List[Dict[str, Any]]:
        """IRI por setor censitário — malha fina para mapa temático."""
        muni = db.query(Municipio).filter(Municipio.id == municipio_id).first()
        if not muni:
            return []
        muni_shape = AnalyticalEngine._shape_from_db_geometry(db, muni.geom)
        water_rows = db.query(CoberturaVegetalMapBiomas).filter(
            CoberturaVegetalMapBiomas.municipio_id == municipio_id,
            CoberturaVegetalMapBiomas.classe_uso == "Corpo d'água",
        ).all()
        flood_events = db.query(HistoricoDesastreS2ID).filter(
            HistoricoDesastreS2ID.municipio_id == municipio_id,
            HistoricoDesastreS2ID.tipo_desastre.in_(["Inundação", "Alagamento Urbano"]),
        ).all()
        urban_cover = db.query(CoberturaVegetalMapBiomas).filter(
            CoberturaVegetalMapBiomas.municipio_id == municipio_id,
            CoberturaVegetalMapBiomas.classe_uso == "Área Urbana",
        ).all()
        setores = db.query(SetorCensitario).filter(SetorCensitario.municipio_id == municipio_id).all()
        results: list[dict[str, Any]] = []
        for s in setores:
            metrics = AnalyticalEngine._iri_for_unit(
                db,
                municipio_id,
                s.geom,
                muni_shape,
                water_rows,
                flood_events=flood_events,
                urban_cover=urban_cover,
            )
            results.append({
                "id": s.id,
                "codigo_setor": s.codigo_setor,
                "nome": f"Setor {s.codigo_setor[-4:]}",
                **metrics,
            })
        return results

    @staticmethod
    def calculate_climate_vulnerability_setores(db: Session, municipio_id: int) -> List[Dict[str, Any]]:
        """IVC por setor censitário — mesma lógica relativa do IVC por bairro."""
        muni = db.query(Municipio).filter(Municipio.id == municipio_id).first()
        if not muni:
            return []
        setores = db.query(SetorCensitario).filter(SetorCensitario.municipio_id == municipio_id).all()
        if not setores:
            return []

        muni_area = AnalyticalEngine._bairro_area_km2(db, muni.geom)
        muni_pop = int(muni.populacao or 0) or 1
        urban_cover = db.query(CoberturaVegetalMapBiomas).filter(
            CoberturaVegetalMapBiomas.municipio_id == municipio_id,
            CoberturaVegetalMapBiomas.classe_uso == "Área Urbana",
        ).all()
        forest_cover = db.query(CoberturaVegetalMapBiomas).filter(
            CoberturaVegetalMapBiomas.municipio_id == municipio_id,
            CoberturaVegetalMapBiomas.classe_uso == "Vegetação / Floresta",
        ).all()

        raw_rows: list[dict[str, Any]] = []
        densities: list[float] = []
        incomes: list[float] = []

        for s in setores:
            area_km2 = max(AnalyticalEngine._bairro_area_km2(db, s.geom), 0.01)
            pop_raw = int(s.populacao or 0)
            pop_est = int(round(muni_pop * (area_km2 / muni_area))) if muni_area > 0 else pop_raw
            pop = pop_raw if pop_raw > 0 else pop_est
            avg_income = float(s.renda_media or 1500.0)
            density = pop / area_km2 if area_km2 > 0 else 0.0

            disasters_count = db.query(HistoricoDesastreS2ID).filter(
                HistoricoDesastreS2ID.municipio_id == municipio_id,
                func.ST_Intersects(s.geom, HistoricoDesastreS2ID.geom),
            ).count()
            active_alerts = db.query(AlertaCemaden).filter(
                AlertaCemaden.municipio_id == municipio_id,
                func.ST_Intersects(s.geom, AlertaCemaden.geom),
            ).all()
            alert_weight = 0.0
            for alt in active_alerts:
                nivel = str(getattr(alt, "nivel_alerta", "") or "").upper()
                if nivel in {"MUITO_ALTO", "VERMELHO"}:
                    alert_weight = max(alert_weight, 1.0)
                elif nivel in {"ALTO", "LARANJA"}:
                    alert_weight = max(alert_weight, 0.8)
                elif nivel in {"MEDIO", "MÉDIO", "AMARELO"}:
                    alert_weight = max(alert_weight, 0.5)
                elif nivel in {"BAIXO", "VERDE"}:
                    alert_weight = max(alert_weight, 0.2)

            area_deg = db.scalar(func.ST_Area(s.geom)) or 0.0
            urban_pct = (
                float(AnalyticalEngine._covered_area_deg(db, s.geom, urban_cover)) / float(area_deg)
                if area_deg else 0.5
            )
            veg_pct = (
                float(AnalyticalEngine._covered_area_deg(db, s.geom, forest_cover)) / float(area_deg)
                if area_deg else 0.0
            )
            hospitals_count = db.query(InfraestruturaUrbana).filter(
                InfraestruturaUrbana.tipo == "hospital",
                func.ST_Intersects(s.geom, InfraestruturaUrbana.geom),
            ).count()

            densities.append(float(density))
            incomes.append(float(avg_income))
            raw_rows.append({
                "s": s,
                "area_km2": area_km2,
                "populacao": pop,
                "pop_raw": pop_raw,
                "pop_est_area": pop_est,
                "renda_media": avg_income,
                "density": density,
                "disasters_count": int(disasters_count),
                "alert_weight": alert_weight,
                "urban_pct": urban_pct,
                "veg_pct": veg_pct,
                "hospitais_count": int(hospitals_count),
            })

        pop_sum = sum(int(r["pop_raw"] or 0) for r in raw_rows)
        use_area_pop = pop_sum > muni_pop * 1.35
        if use_area_pop:
            densities = []
            for r in raw_rows:
                r["populacao"] = int(r["pop_est_area"])
                r["density"] = r["populacao"] / r["area_km2"] if r["area_km2"] > 0 else 0.0
                densities.append(float(r["density"]))

        density_ranks = AnalyticalEngine._percentile_ranks(densities)
        income_sensitivity = [1.0 - r for r in AnalyticalEngine._percentile_ranks(incomes)]

        results: list[dict[str, Any]] = []
        for idx, r in enumerate(raw_rows):
            sensibilidade = (density_ranks[idx] * 0.55) + (income_sensitivity[idx] * 0.45)
            disaster_score = min(r["disasters_count"] / 5.0, 1.0)
            exposicao = (
                disaster_score * 0.35
                + float(r["alert_weight"]) * 0.25
                + min(float(r["urban_pct"]), 1.0) * 0.40
            )
            capacidade_adaptacao = (
                min(float(r["veg_pct"]) * 3.0, 1.0) * 0.6
                + min(r["hospitais_count"] / 2.0, 1.0) * 0.4
            )
            ivc = (exposicao + sensibilidade) / 2.0
            ivc = ivc * (1.0 - (capacidade_adaptacao * 0.3))
            ivc = round(max(0.0, min(1.0, ivc)), 2)
            s = r["s"]
            results.append({
                "id": s.id,
                "codigo_setor": s.codigo_setor,
                "nome": f"Setor {s.codigo_setor[-4:]}",
                "exposicao": round(exposicao, 2),
                "sensibilidade": round(sensibilidade, 2),
                "capacidade_adaptacao": round(capacidade_adaptacao, 2),
                "indice_vulnerabilidade": ivc,
            })
        return results

    @staticmethod
    def calculate_flood_risk(db: Session, municipio_id: int) -> List[Dict[str, Any]]:
        """
        Calculates the Flood Risk Index (IRI) for all neighborhoods.
        IRI = (S2ID Floods History * 0.4) + (Impervious Surface Cover * 0.4) + (Water body proximity * 0.2)
        """
        bairros = db.query(Bairro).filter(Bairro.municipio_id == municipio_id).all()
        results = []
        muni = db.query(Municipio).filter(Municipio.id == municipio_id).first()
        muni_shape = AnalyticalEngine._shape_from_db_geometry(db, muni.geom) if muni else None
        if muni_shape is None:
            return []

        water_rows = db.query(CoberturaVegetalMapBiomas).filter(
            CoberturaVegetalMapBiomas.municipio_id == municipio_id,
            CoberturaVegetalMapBiomas.classe_uso == "Corpo d'água",
        ).all()
        flood_events = db.query(HistoricoDesastreS2ID).filter(
            HistoricoDesastreS2ID.municipio_id == municipio_id,
            HistoricoDesastreS2ID.tipo_desastre.in_(["Inundação", "Alagamento Urbano"]),
        ).all()
        urban_cover = db.query(CoberturaVegetalMapBiomas).filter(
            CoberturaVegetalMapBiomas.municipio_id == municipio_id,
            CoberturaVegetalMapBiomas.classe_uso == "Área Urbana",
        ).all()

        # Pré-processa geometrias uma vez (evita unary_union/parse por bairro).
        flood_pts = []
        for ev in flood_events:
            try:
                flood_pts.append(
                    AnalyticalEngine._repair_shape(
                        AnalyticalEngine._shape_from_db_geometry(db, ev.geom)
                    )
                )
            except Exception:
                continue
        urban_merged = AnalyticalEngine._safe_unary_union(
            [
                AnalyticalEngine._shape_from_db_geometry(db, row.geom)
                for row in urban_cover
            ]
        )
        water_merged = AnalyticalEngine._safe_unary_union(
            [
                AnalyticalEngine._shape_from_db_geometry(db, row.geom)
                for row in water_rows
            ]
        )

        minx, miny, maxx, maxy = muni_shape.bounds
        max_ref = max(((maxx - minx) ** 2 + (maxy - miny) ** 2) ** 0.5 * 0.4, 0.004)

        for b in bairros:
            try:
                unit = AnalyticalEngine._repair_shape(
                    AnalyticalEngine._shape_from_db_geometry(db, b.geom)
                )
            except Exception:
                continue
            if unit is None or unit.is_empty:
                continue

            flood_disasters = sum(1 for pt in flood_pts if pt is not None and unit.intersects(pt))
            s2id_score = min(flood_disasters / 3.0, 1.0)

            area = float(unit.area) or 1e-12
            if urban_merged is not None and not urban_merged.is_empty:
                try:
                    urban_pct = min(1.0, float(unit.intersection(urban_merged).area) / area)
                except Exception:
                    urban_pct = 0.5
            else:
                urban_pct = 0.5
            impermeabilizacao_score = urban_pct

            if water_merged is None or water_merged.is_empty:
                water_score = 0.25
            elif unit.intersects(water_merged):
                water_score = 1.0
            else:
                dist = unit.centroid.distance(water_merged)
                water_score = round(max(0.2, min(1.0, 1.0 - dist / max_ref)), 2)

            iri = (s2id_score * 0.4) + (impermeabilizacao_score * 0.4) + (water_score * 0.2)
            iri = round(max(0.0, min(1.0, iri)), 2)
            results.append({
                "id": b.id,
                "bairro_nome": b.nome,
                "s2id_historico_score": round(s2id_score, 2),
                "impermeabilizacao_score": round(impermeabilizacao_score, 2),
                "hidrografia_proximidade_score": water_score,
                "indice_risco_inundacao": iri,
            })

        return results

    @staticmethod
    def run_impermeabilizacao_simulation(db: Session, muni_id: int, taxa_adicional: float) -> Dict[str, Any]:
        """
        Simulates the impact of additional soil waterproofing (e.g. +30% urban construction).
        Calculates the expanded inundation area and affected population.
        """
        # Load municipal boundary
        muni = db.query(Municipio).filter(Municipio.id == muni_id).first()
        bairros = db.query(Bairro).filter(Bairro.municipio_id == muni_id).all()
        muni_shape = shape(json.loads(db.scalar(muni.geom.ST_AsGeoJSON())))
        
        # We model the flood footprint using a buffer around the water bodies.
        # With additional waterproofing, the water runoff expands the buffer width.
        base_water_bodies = db.query(CoberturaVegetalMapBiomas.geom).filter(
            CoberturaVegetalMapBiomas.municipio_id == muni_id,
            CoberturaVegetalMapBiomas.classe_uso == "Corpo d'água"
        ).all()
        
        # Parse water body geometries into shapely objects
        geom_shapes = []
        for wb in base_water_bodies:
            g_dict = json.loads(db.scalar(wb.geom.ST_AsGeoJSON()))
            geom_shapes.append(shape(g_dict))
            
        if not geom_shapes:
            from shapely.geometry import LineString
            minx, miny, maxx, maxy = muni_shape.bounds
            midy = (miny + maxy) / 2
            geom_shapes.append(LineString([(minx, midy), ((minx + maxx) / 2, midy), (maxx, midy)]))

        combined_rivers = unary_union(geom_shapes)
        
        # Calculate expanded flood buffer based on waterproofing percentage
        # 1% additional = +10 meters (approx 0.0001 degrees)
        buffer_width_deg = 0.0002 + (taxa_adicional * 0.00003)
        flood_footprint = combined_rivers.buffer(buffer_width_deg)
        
        # Let's see which bairros intersect the flood footprint and estimate the population affected
        affected_bairros = []
        affected_pop = 0
        total_affected_area_deg = 0.0
        
        for b in bairros:
            b_geom_dict = json.loads(db.scalar(b.geom.ST_AsGeoJSON()))
            b_geom = shape(b_geom_dict)
            
            intersect = b_geom.intersection(flood_footprint)
            if not intersect.is_empty:
                affected_bairros.append(b.nome)
                # Area of intersection
                intersect_area_deg = intersect.area
                total_affected_area_deg += intersect_area_deg
                
                # Fetch population of sectors in this neighborhood to estimate affected citizens
                sectors = db.query(SetorCensitario).filter(
                    SetorCensitario.municipio_id == muni_id,
                    func.ST_Intersects(b.geom, SetorCensitario.geom)
                ).all()
                
                # Estimate ratio of neighborhood flooded
                b_area = b_geom.area
                flood_ratio = intersect_area_deg / b_area if b_area > 0 else 0
                
                b_pop = sum(s.populacao for s in sectors)
                affected_pop += int(b_pop * flood_ratio * 1.5) # multiplier for flood density
                
        # Format flood footprint geometry as GeoJSON FeatureCollection
        fc = {
            "type": "FeatureCollection",
            "features": [
                {
                    "type": "Feature",
                    "geometry": mapping(flood_footprint),
                    "properties": {
                        "name": "Mancha de Inundação Simulada",
                        "impact_type": "Impermeabilização",
                        "intensity_pct": taxa_adicional
                    }
                }
            ]
        }
        
        affected_area_km2 = total_affected_area_deg * 12300.0
        
        return {
            "scenario_type": "Waterproofing",
            "input_value": taxa_adicional,
            "metric_impact": "População sob risco de inundação",
            "impact_value": min(affected_pop, muni.populacao),
            "affected_area_km2": round(affected_area_km2, 2),
            "affected_population": min(affected_pop, muni.populacao),
            "affected_bairros": affected_bairros,
            "geometry": fc
        }

    @staticmethod
    def run_perda_vegetacao_simulation(db: Session, muni_id: int, taxa_desmatamento: float) -> Dict[str, Any]:
        """
        Simulates the temperature increase due to canopy/vegetation loss.
        Formula: Temp Increase = 0.05 * taxa_desmatamento (°C).
        Generates heat island intensity polygons.
        """
        muni = db.query(Municipio).filter(Municipio.id == muni_id).first()
        bairros = db.query(Bairro).filter(Bairro.municipio_id == muni_id).all()
        
        # Fetch current forests
        forests = db.query(CoberturaVegetalMapBiomas.geom).filter(
            CoberturaVegetalMapBiomas.municipio_id == muni_id,
            CoberturaVegetalMapBiomas.classe_uso == "Vegetação / Floresta"
        ).all()
        
        forest_shapes = []
        for f in forests:
            g_dict = json.loads(db.scalar(f.geom.ST_AsGeoJSON()))
            forest_shapes.append(shape(g_dict))
            
        if not forest_shapes:
            from shapely.geometry import Point
            muni_shape = shape(json.loads(db.scalar(muni.geom.ST_AsGeoJSON())))
            forest_shapes.append(Point(muni_shape.centroid.x, muni_shape.centroid.y).buffer(0.02))
            
        combined_forests = unary_union(forest_shapes)
        
        # Calculate temperature increase
        temp_increase = taxa_desmatamento * 0.04  # e.g., 50% desmatamento = +2.0 °C
        
        # Build heat island zones: areas surrounding urban points, expanding into lost forest zones
        # We represent this as a buffer around urban centers intersecting the municipal boundaries.
        urban_centers = db.query(CoberturaVegetalMapBiomas.geom).filter(
            CoberturaVegetalMapBiomas.municipio_id == muni_id,
            CoberturaVegetalMapBiomas.classe_uso == "Área Urbana"
        ).all()
        
        urban_shapes = []
        for u in urban_centers:
            g_dict = json.loads(db.scalar(u.geom.ST_AsGeoJSON()))
            urban_shapes.append(shape(g_dict))
            
        if not urban_shapes:
            from shapely.geometry import Point
            muni_shape = shape(json.loads(db.scalar(muni.geom.ST_AsGeoJSON())))
            urban_shapes.append(Point(muni_shape.centroid.x, muni_shape.centroid.y).buffer(0.02))
            
        combined_urban = unary_union(urban_shapes)
        
        # Heat islands expand by buffer size depending on deforestation
        heat_island = combined_urban.buffer(taxa_desmatamento * 0.0001)
        
        # Intersect with municipal boundary
        muni_geom_dict = json.loads(db.scalar(muni.geom.ST_AsGeoJSON()))
        muni_shape = shape(muni_geom_dict)
        heat_island_bounded = heat_island.intersection(muni_shape)
        
        # Identify affected bairros and population
        affected_bairros = []
        affected_pop = 0
        
        for b in bairros:
            b_geom_dict = json.loads(db.scalar(b.geom.ST_AsGeoJSON()))
            b_geom = shape(b_geom_dict)
            
            intersect = b_geom.intersection(heat_island_bounded)
            if not intersect.is_empty:
                affected_bairros.append(b.nome)
                # Calculate ratio of neighborhood inside heat island
                b_area = b_geom.area
                ratio = intersect.area / b_area if b_area > 0 else 0
                
                # Fetch population
                sectors = db.query(SetorCensitario).filter(
                    SetorCensitario.municipio_id == muni_id,
                    func.ST_Intersects(b.geom, SetorCensitario.geom)
                ).all()
                b_pop = sum(s.populacao for s in sectors)
                affected_pop += int(b_pop * ratio)

        fc = {
            "type": "FeatureCollection",
            "features": [
                {
                    "type": "Feature",
                    "geometry": mapping(heat_island_bounded),
                    "properties": {
                        "name": "Ilha de Calor Simulada",
                        "temp_increase_celsius": round(temp_increase, 2),
                        "deforestation_rate": taxa_desmatamento
                    }
                }
            ]
        }
        
        return {
            "scenario_type": "VegetationLoss",
            "input_value": taxa_desmatamento,
            "metric_impact": "Aumento médio da temperatura local (°C)",
            "impact_value": round(temp_increase, 2),
            "affected_area_km2": round(heat_island_bounded.area * 12300.0, 2),
            "affected_population": min(affected_pop, muni.populacao),
            "affected_bairros": affected_bairros,
            "geometry": fc
        }

    @staticmethod
    def _impact_from_hazard(
        db: Session,
        muni_id: int,
        muni: Municipio,
        bairros: list,
        hazard_geom,
        intensity_factor: float = 1.0,
        *,
        min_exposure_ratio: float = 0.02,
    ) -> tuple[list[str], int, list[dict[str, Any]]]:
        """Calcula bairros e população expostos a partir da geometria final de risco."""
        exposures: list[dict[str, Any]] = []
        affected_pop = 0

        for b in bairros:
            b_geom = shape(json.loads(db.scalar(b.geom.ST_AsGeoJSON())))
            intersect = b_geom.intersection(hazard_geom)
            if intersect.is_empty:
                continue

            ratio = intersect.area / b_geom.area if b_geom.area > 0 else 0.0
            if ratio < min_exposure_ratio:
                continue

            sectors = db.query(SetorCensitario).filter(
                SetorCensitario.municipio_id == muni_id,
                func.ST_Intersects(b.geom, SetorCensitario.geom),
            ).all()
            b_pop = sum(s.populacao for s in sectors)
            pop_exposed = int(b_pop * ratio * intensity_factor)
            affected_pop += pop_exposed
            exposures.append({
                "bairro": b.nome,
                "exposicao_pct": round(ratio * 100.0, 1),
                "populacao_exposta": pop_exposed,
            })

        exposures.sort(key=lambda row: (row["exposicao_pct"], row["populacao_exposta"]), reverse=True)
        affected_bairros = [row["bairro"] for row in exposures]
        cap = muni.populacao or affected_pop
        return affected_bairros, min(affected_pop, cap), exposures

    @staticmethod
    def run_chuva_extrema_simulation(
        db: Session,
        muni_id: int,
        precipitacao_mm: float,
        *,
        impermeability_offset: float = 0.0,
        nivel_mar_m: float = 0.0,
        chuva_antecedente_mm: float = 0.0,
        sea_level_meta: dict | None = None,
        drain_removed_mm: float = 0.0,
        rede_saturada: bool = False,
        drenagem_meta: dict | None = None,
        duracao_h: float = 1.0,
    ) -> Dict[str, Any]:
        """
        Simula chuva extrema com DEM SRTM, IRI por bairro, deslizamento por declividade×chuva
        e métricas recalculadas após união das manchas finais.
        """
        from app.services.hydro_simulator import enrich_rainfall_simulation

        muni = db.query(Municipio).filter(Municipio.id == muni_id).first()
        bairros = db.query(Bairro).filter(Bairro.municipio_id == muni_id).all()
        muni_shape = shape(json.loads(db.scalar(muni.geom.ST_AsGeoJSON())))

        terrain = enrich_rainfall_simulation(
            db,
            muni,
            precipitacao_mm,
            impermeability_offset=impermeability_offset,
            nivel_mar_m=nivel_mar_m,
            chuva_antecedente_mm=chuva_antecedente_mm,
            sea_level_meta=sea_level_meta,
            drain_removed_mm=drain_removed_mm,
            rede_saturada=rede_saturada,
            drenagem_meta=drenagem_meta,
            duracao_h=duracao_h,
        )
        flood_bands = terrain.get("flood_bands")
        intensity = 1.2 + (precipitacao_mm / 100.0)

        if flood_bands and flood_bands.get("features"):
            flood_only = [
                f for f in flood_bands["features"]
                if f.get("properties", {}).get("layer_type") == "flood_band"
            ]
            hazard_shapes = [shape(f["geometry"]) for f in flood_only]
            final_hazards = (
                unary_union(hazard_shapes).intersection(muni_shape)
                if hazard_shapes
                else muni_shape.centroid.buffer(0.000001)
            )
            fc = flood_bands
        else:
            # Fallback heurístico quando DEM indisponível
            rivers = db.query(CoberturaVegetalMapBiomas.geom).filter(
                CoberturaVegetalMapBiomas.municipio_id == muni_id,
                CoberturaVegetalMapBiomas.classe_uso == "Corpo d'água",
            ).all()
            river_shapes = [
                shape(json.loads(db.scalar(r.geom.ST_AsGeoJSON()))) for r in rivers
            ]
            if not river_shapes:
                from shapely.geometry import LineString
                minx, miny, maxx, maxy = muni_shape.bounds
                midy = (miny + maxy) / 2
                river_shapes.append(LineString([(minx, midy), ((minx + maxx) / 2, midy), (maxx, midy)]))

            buffer_width_deg = (precipitacao_mm / 100.0) * 0.0008
            final_hazards = unary_union(river_shapes).buffer(buffer_width_deg).intersection(muni_shape)
            fc = {
                "type": "FeatureCollection",
                "features": [{
                    "type": "Feature",
                    "geometry": mapping(final_hazards),
                    "properties": {
                        "layer_type": "flood_band",
                        "depth_band": "moderada",
                        "name": "Mancha de Risco Pluvial (heurística)",
                        "precipitation_mm": precipitacao_mm,
                        "fill_color": "#0284c7",
                    },
                }],
            }

        affected_bairros, affected_pop, bairro_exposures = AnalyticalEngine._impact_from_hazard(
            db, muni_id, muni, bairros, final_hazards, intensity_factor=intensity,
        )

        sim_meta = terrain.get("simulation_meta") or {}
        if bairro_exposures:
            sim_meta = {
                **sim_meta,
                "bairros_exposicao": bairro_exposures[:12],
                "bairros_atingidos_count": len(bairro_exposures),
            }

        # 17g.2e / 17g.2a — selo de confiança + validação contra histórico S2ID
        try:
            from app.services.simulation_confidence_service import enrich_simulation_confidence

            sim_meta = enrich_simulation_confidence(
                db,
                muni,
                sim_meta,
                flood_geometry=fc,
                affected_bairros=affected_bairros,
            )
        except Exception as exc:
            import logging

            logging.getLogger(__name__).warning("Selo/validação S2ID falhou: %s", exc)

        # 17b.1 / 17b.5 — inundação × edifício + painel de exposição do cenário
        try:
            from app.services.building_exposure_service import enrich_simulation_building_exposure

            sim_meta = enrich_simulation_building_exposure(
                db,
                muni,
                sim_meta,
                flood_geometry=fc,
                affected_population=affected_pop,
                precipitacao_mm=precipitacao_mm,
            )
        except Exception as exc:
            import logging

            logging.getLogger(__name__).warning("Exposição edifícios falhou: %s", exc)

        affected_area_km2 = round(final_hazards.area * 12300.0, 2)

        # Impactos operacionais: escoamento, mobilidade, âncora histórica
        try:
            from app.services.rainfall_event_anchors import (
                estimate_operational_impacts,
                match_anchor,
            )

            dmeta = drenagem_meta or {}
            sim_meta["impacto_operacional"] = estimate_operational_impacts(
                precip_mm=float(precipitacao_mm),
                max_depth_m=float(sim_meta.get("max_depth_m") or 0.0),
                affected_area_km2=float(affected_area_km2),
                affected_population=int(affected_pop or 0),
                landslide_zones=int(sim_meta.get("landslide_zones") or 0),
                drainage_cap_mm_h=float(
                    dmeta.get("capacidade_mm_h") or dmeta.get("capacidade") or 18.0
                ),
                drain_removed_mm=float(drain_removed_mm or dmeta.get("removido_mm") or 0.0),
                drenagem_aplicada=bool(dmeta.get("aplicado", True)),
                hydrograph_duration_h=float(sim_meta.get("hydrograph_duration_h") or 6.0),
                duracao_h=float(duracao_h or 1.0),
            )
            anchor = match_anchor(muni.codigo_ibge, float(precipitacao_mm), duracao_h=float(duracao_h or 1.0))
            if anchor:
                sim_meta["ancora_historica"] = anchor
        except Exception as exc:
            import logging

            logging.getLogger(__name__).warning("Impacto operacional / âncora falhou: %s", exc)

        vias_fc = None
        try:
            from app.services.impassable_roads_service import build_impassable_roads_geojson

            vias_fc, vias_meta = build_impassable_roads_geojson(db, muni, fc)
            mob = (sim_meta.get("impacto_operacional") or {}).setdefault("mobilidade", {})
            if vias_meta.get("ok") and vias_meta.get("vias_comprometidas_km") is not None:
                mob["vias_comprometidas_km"] = vias_meta["vias_comprometidas_km"]
                mob["vias_comprometidas_km_proxy"] = vias_meta["vias_comprometidas_km"]
                mob["vias_fonte"] = vias_meta.get("fonte_vias")
                mob["vias_trechos"] = vias_meta.get("trechos")
            else:
                mob["vias_fonte"] = vias_meta.get("reason") or "indisponivel"
        except Exception as exc:
            import logging

            logging.getLogger(__name__).warning("Vias intransitáveis falhou: %s", exc)

        ativos_fc = None
        try:
            from app.services.critical_assets_flood_service import build_critical_assets_hit_geojson

            ativos_fc, ativos_meta = build_critical_assets_hit_geojson(db, muni, fc)
            sim_meta["ativos_criticos"] = ativos_meta
            ops = sim_meta.setdefault("impacto_operacional", {})
            ops["ativos_criticos"] = {
                "escolas": ativos_meta.get("escolas", 0),
                "saude": ativos_meta.get("saude", 0),
                "abrigos": ativos_meta.get("abrigos", 0),
                "total": ativos_meta.get("total", 0),
                "matriculas_expostas": ativos_meta.get("matriculas_expostas", 0),
                "leitos_sus_expostos": ativos_meta.get("leitos_sus_expostos", 0),
            }
        except Exception as exc:
            import logging

            logging.getLogger(__name__).warning("Ativos críticos × mancha falhou: %s", exc)

        try:
            from app.services.glofas_compare_service import compare_flood_to_glofas

            sim_meta["glofas_compare"] = compare_flood_to_glofas(db, muni.codigo_ibge, fc)
        except Exception as exc:
            import logging

            logging.getLogger(__name__).warning("Comparativo GloFAS falhou: %s", exc)

        return {
            "scenario_type": "ExtremeRainfall",
            "input_value": precipitacao_mm,
            "metric_impact": "População em áreas de alto risco de desastre",
            "impact_value": affected_pop,
            "affected_area_km2": affected_area_km2,
            "affected_population": affected_pop,
            "affected_bairros": affected_bairros,
            "geometry": fc,
            "contours": terrain.get("contours"),
            "flow_paths": terrain.get("flow_paths"),
            "vias_intransitaveis": vias_fc,
            "ativos_criticos_atingidos": ativos_fc,
            "simulation_meta": sim_meta,
            "risk_context": terrain.get("risk_context"),
        }

    @staticmethod
    def run_drenagem_simulation(db: Session, muni_id: int, deficit_drenagem_pct: float) -> Dict[str, Any]:
        """
        Simulates reduced drainage performance. It uses flood-risk scores, urban
        cover and proximity to water bodies already available in the internal version.
        """
        muni = db.query(Municipio).filter(Municipio.id == muni_id).first()
        bairros = db.query(Bairro).filter(Bairro.municipio_id == muni_id).all()
        flood_risk = {
            item["bairro_nome"]: item
            for item in AnalyticalEngine.calculate_flood_risk(db, muni_id)
        }

        water_bodies = db.query(CoberturaVegetalMapBiomas.geom).filter(
            CoberturaVegetalMapBiomas.municipio_id == muni_id,
            CoberturaVegetalMapBiomas.classe_uso == "Corpo d'água"
        ).all()

        water_shapes = []
        for wb in water_bodies:
            water_shapes.append(shape(json.loads(db.scalar(wb.geom.ST_AsGeoJSON()))))

        if not water_shapes:
            from shapely.geometry import Point
            muni_shape = shape(json.loads(db.scalar(muni.geom.ST_AsGeoJSON())))
            water_shapes.append(muni_shape.centroid.buffer(0.01))

        combined_water = unary_union(water_shapes)
        deficit_factor = max(0.0, min(deficit_drenagem_pct / 100.0, 1.0))
        affected_bairros = []
        affected_pop = 0
        exposed_shapes = []

        for b in bairros:
            b_geom = shape(json.loads(db.scalar(b.geom.ST_AsGeoJSON())))
            risk = flood_risk.get(b.nome, {})
            risk_score = float(risk.get("indice_risco_inundacao", 0.0))
            urban_score = float(risk.get("impermeabilizacao_score", 0.5))

            drainage_pressure = (risk_score * 0.55) + (urban_score * 0.25) + (deficit_factor * 0.20)
            if drainage_pressure < 0.35:
                continue

            centroid_distance = b_geom.centroid.distance(combined_water)
            proximity_boost = 1.0 if centroid_distance < 0.03 else 0.65
            local_buffer = 0.0006 + (deficit_factor * 0.0025 * drainage_pressure * proximity_boost)
            drainage_zone = b_geom.intersection(combined_water.buffer(local_buffer))
            if drainage_zone.is_empty:
                drainage_zone = b_geom.centroid.buffer(local_buffer).intersection(b_geom)

            if drainage_zone.is_empty:
                continue

            affected_bairros.append(b.nome)
            exposed_shapes.append(drainage_zone)
            ratio = drainage_zone.area / b_geom.area if b_geom.area > 0 else 0
            sectors = db.query(SetorCensitario).filter(
                SetorCensitario.municipio_id == muni_id,
                func.ST_Intersects(b.geom, SetorCensitario.geom)
            ).all()
            b_pop = sum(s.populacao for s in sectors)
            affected_pop += int(b_pop * ratio * (1.0 + deficit_factor))

        if exposed_shapes:
            final_zone = unary_union(exposed_shapes)
        else:
            muni_shape = shape(json.loads(db.scalar(muni.geom.ST_AsGeoJSON())))
            final_zone = muni_shape.centroid.buffer(0.000001)

        fc = {
            "type": "FeatureCollection",
            "features": [
                {
                    "type": "Feature",
                    "geometry": mapping(final_zone),
                    "properties": {
                        "name": "Mancha de Déficit de Drenagem Simulada",
                        "drainage_deficit_pct": deficit_drenagem_pct,
                        "description": "Zonas estimadas por risco de inundação, área urbana, proximidade hídrica e déficit operacional informado."
                    }
                }
            ]
        }

        return {
            "scenario_type": "DrainageDeficit",
            "input_value": deficit_drenagem_pct,
            "metric_impact": "População exposta a falhas de drenagem",
            "impact_value": min(affected_pop, muni.populacao),
            "affected_area_km2": round(final_zone.area * 12300.0, 2),
            "affected_population": min(affected_pop, muni.populacao),
            "affected_bairros": affected_bairros,
            "geometry": fc
        }

    @staticmethod
    def _fiscal_capacity_score(fiscal_row) -> float:
        if not fiscal_row:
            return 0.4
        score = 0.5
        capag = (fiscal_row.nota_capag or "").upper()
        if capag in {"A", "B"}:
            score += 0.25
        elif capag in {"C", "D"}:
            score -= 0.15
        rcl = float(fiscal_row.receita_corrente_liquida or 0)
        if rcl > 500_000_000:
            score += 0.15
        elif rcl > 50_000_000:
            score += 0.05
        return max(0.0, min(1.0, score))

    @staticmethod
    def calculate_multidimensional_vulnerability(db: Session, municipio_id: int) -> List[Dict[str, Any]]:
        """
        VM = 0.30×risco_climático + 0.25×vulnerabilidade_social + 0.20×cobertura_saude_inv
             + 0.15×cobertura_seguranca_inv + 0.10×capacidade_fiscal_inv
        """
        muni = db.query(Municipio).filter(Municipio.id == municipio_id).first()
        if not muni:
            return []

        vuln = AnalyticalEngine.calculate_climate_vulnerability(db, municipio_id)
        floods = AnalyticalEngine.calculate_flood_risk(db, municipio_id)
        vuln_map = {v["id"]: v for v in vuln}
        flood_map = {f["id"]: f for f in floods}

        saude = db.query(MunicipioSaude).filter(MunicipioSaude.codigo_ibge == muni.codigo_ibge).first()
        seguranca = (
            db.query(MunicipioSeguranca)
            .filter(MunicipioSeguranca.codigo_ibge == muni.codigo_ibge)
            .order_by(MunicipioSeguranca.mes_ref.desc())
            .first()
        )
        fiscal = db.query(MunicipioFiscal).filter(MunicipioFiscal.codigo_ibge == muni.codigo_ibge).first()

        saude_score = float(saude.cobertura_saude_score) if saude and saude.cobertura_saude_score is not None else 0.45
        seg_score = float(seguranca.cobertura_seguranca_score) if seguranca and seguranca.cobertura_seguranca_score is not None else 0.45
        fiscal_score = AnalyticalEngine._fiscal_capacity_score(fiscal)

        saude_inv = 1.0 - saude_score
        seg_inv = 1.0 - seg_score
        fiscal_inv = 1.0 - fiscal_score

        high_risk_bairro = max(vuln, key=lambda x: x["indice_vulnerabilidade"], default=None)
        high_risk_id = high_risk_bairro["id"] if high_risk_bairro else None
        high_risk_geom = None
        if high_risk_id:
            hr = db.query(Bairro).filter(Bairro.id == high_risk_id).first()
            if hr:
                high_risk_geom = shape(json.loads(db.scalar(hr.geom.ST_AsGeoJSON())))

        bairros = db.query(Bairro).filter(Bairro.municipio_id == municipio_id).all()
        results = []

        for b in bairros:
            v = vuln_map.get(b.id, {})
            f = flood_map.get(b.id, {})
            risco_climatico = (float(v.get("indice_vulnerabilidade", 0)) * 0.55) + (float(f.get("indice_risco_inundacao", 0)) * 0.45)
            vulnerabilidade_social = float(v.get("indice_vulnerabilidade", 0))

            vm = (
                0.30 * risco_climatico
                + 0.25 * vulnerabilidade_social
                + 0.20 * saude_inv
                + 0.15 * seg_inv
                + 0.10 * fiscal_inv
            )
            vm = round(min(1.0, max(0.0, vm)), 3)

            dist_risco_km = None
            if high_risk_geom:
                b_geom = shape(json.loads(db.scalar(b.geom.ST_AsGeoJSON())))
                dist_risco_km = round(b_geom.centroid.distance(high_risk_geom.centroid) * 111.0, 2)

            flag_multi = vm >= 0.66 and risco_climatico >= 0.55 and (saude_inv >= 0.5 or seg_inv >= 0.5)

            results.append({
                "id": b.id,
                "bairro_nome": b.nome,
                "indice_vm": vm,
                "risco_climatico": round(risco_climatico, 3),
                "vulnerabilidade_social": round(vulnerabilidade_social, 3),
                "cobertura_saude_inv": round(saude_inv, 3),
                "cobertura_seguranca_inv": round(seg_inv, 3),
                "capacidade_fiscal_inv": round(fiscal_inv, 3),
                "vulnerabilidade_multidimensional": flag_multi,
                "distancia_bairro_risco_km": dist_risco_km,
            })

        return results

    @staticmethod
    def calculate_multidimensional_vulnerability_setores(db: Session, municipio_id: int) -> List[Dict[str, Any]]:
        """VM por setor censitário com gradiente socioespacial e classes relativas."""
        muni = db.query(Municipio).filter(Municipio.id == municipio_id).first()
        if not muni:
            return []

        vuln = {
            item["id"]: item
            for item in AnalyticalEngine.calculate_climate_vulnerability_setores(db, municipio_id)
        }
        floods = {
            item["id"]: item
            for item in AnalyticalEngine.calculate_flood_risk_setores(db, municipio_id)
        }

        saude = db.query(MunicipioSaude).filter(MunicipioSaude.codigo_ibge == muni.codigo_ibge).first()
        seguranca = (
            db.query(MunicipioSeguranca)
            .filter(MunicipioSeguranca.codigo_ibge == muni.codigo_ibge)
            .order_by(MunicipioSeguranca.mes_ref.desc())
            .first()
        )
        fiscal = db.query(MunicipioFiscal).filter(MunicipioFiscal.codigo_ibge == muni.codigo_ibge).first()

        saude_score = float(saude.cobertura_saude_score) if saude and saude.cobertura_saude_score is not None else 0.45
        seg_score = float(seguranca.cobertura_seguranca_score) if seguranca and seguranca.cobertura_seguranca_score is not None else 0.45
        fiscal_score = AnalyticalEngine._fiscal_capacity_score(fiscal)
        saude_inv = 1.0 - saude_score
        seg_inv = 1.0 - seg_score
        fiscal_inv = 1.0 - fiscal_score

        setores = db.query(SetorCensitario).filter(SetorCensitario.municipio_id == municipio_id).all()
        raw: list[tuple[int, str, float, float, float, str]] = []

        for setor in setores:
            v = vuln.get(setor.id, {})
            f = floods.get(setor.id, {})
            ivc = float(v.get("indice_vulnerabilidade", 0.4))
            iri = float(f.get("indice_risco_inundacao", 0.4))
            renda = float(setor.renda_media or 1500.0)
            renda_stress = max(0.0, 1.0 - (renda / 4500.0))
            risco_climatico = (ivc * 0.55) + (iri * 0.45)
            vulnerabilidade_social = (ivc * 0.65) + (renda_stress * 0.35)
            vm = (
                0.30 * risco_climatico
                + 0.25 * vulnerabilidade_social
                + 0.20 * saude_inv
                + 0.15 * seg_inv
                + 0.10 * fiscal_inv
            )
            vm = min(1.0, max(0.0, vm))
            geom_json = db.scalar(setor.geom.ST_AsGeoJSON())
            raw.append((setor.id, setor.codigo_setor, vm, risco_climatico, vulnerabilidade_social, geom_json))

        if len(raw) < 3:
            return []

        ordered = sorted(item[2] for item in raw)
        p33 = ordered[max(0, int(round((len(ordered) - 1) * 0.33)))]
        p66 = ordered[max(0, int(round((len(ordered) - 1) * 0.66)))]

        def _classe_vm(val: float) -> str:
            if val >= p66:
                return "CRITICA"
            if val <= p33:
                return "MODERADA"
            return "ALTA"

        results: list[dict[str, Any]] = []
        for sid, codigo, vm, risco_climatico, vulnerabilidade_social, geom_json in raw:
            classe = _classe_vm(vm)
            flag_multi = (
                classe == "CRITICA"
                and risco_climatico >= p66
                and (saude_inv >= 0.45 or seg_inv >= 0.45)
            )
            results.append({
                "id": sid,
                "codigo_setor": codigo,
                "nome": f"Setor {codigo[-4:]}",
                "indice_vm": round(vm, 3),
                "classe_vm": classe,
                "classificacao_relativa": True,
                "risco_climatico": round(risco_climatico, 3),
                "vulnerabilidade_social": round(vulnerabilidade_social, 3),
                "cobertura_saude_inv": round(saude_inv, 3),
                "cobertura_seguranca_inv": round(seg_inv, 3),
                "capacidade_fiscal_inv": round(fiscal_inv, 3),
                "vulnerabilidade_multidimensional": flag_multi,
                "geom_json": geom_json,
                "score_explicacao": (
                    "VM = 30% risco climático + 25% vulnerabilidade social local + 20% gap saúde "
                    "+ 15% gap segurança + 10% gap fiscal. Classe relativa (tertil intra-urbano)."
                ),
            })
        return results

    @staticmethod
    def security_intensity_setores(db: Session, municipio_id: int, taxa_100k: float) -> List[Dict[str, Any]]:
        """Intensidade de segurança por setor — ancora SINESP + gradiente socioespacial."""
        vuln = {
            item["id"]: item
            for item in AnalyticalEngine.calculate_climate_vulnerability_setores(db, municipio_id)
        }
        flood = {
            item["id"]: item
            for item in AnalyticalEngine.calculate_flood_risk_setores(db, municipio_id)
        }
        baseline = min(1.0, taxa_100k / 450.0)
        setores = db.query(SetorCensitario).filter(SetorCensitario.municipio_id == municipio_id).all()
        raw: list[tuple[int, str, float, str, float, float, float]] = []

        for setor in setores:
            ivc = float(vuln.get(setor.id, {}).get("indice_vulnerabilidade", 0.4))
            iri = float(flood.get(setor.id, {}).get("indice_risco_inundacao", 0.4))
            renda = float(setor.renda_media or 1500.0)
            pop = int(setor.populacao or 1000)
            area_deg = db.scalar(func.ST_Area(setor.geom))
            area_km2 = float(area_deg) * 12300.0 if area_deg else 0.01
            density = pop / area_km2 if area_km2 > 0 else 0.0
            density_score = min(1.0, density / 12000.0)
            income_stress = max(0.0, 1.0 - (renda / 4500.0))
            intensidade = min(
                1.0,
                (baseline * 0.22)
                + (income_stress * 0.32)
                + (ivc * 0.26)
                + (density_score * 0.12)
                + (iri * 0.08),
            )
            geom_json = db.scalar(setor.geom.ST_AsGeoJSON())
            raw.append((setor.id, setor.codigo_setor, intensidade, geom_json, ivc, iri, income_stress))

        if len(raw) < 3:
            return []

        ordered = sorted(item[2] for item in raw)
        p33 = ordered[max(0, int(round((len(ordered) - 1) * 0.33)))]
        p66 = ordered[max(0, int(round((len(ordered) - 1) * 0.66)))]

        def _classe(val: float) -> str:
            if val >= p66:
                return "ALTA"
            if val <= p33:
                return "BAIXA"
            return "MEDIA"

        results: list[dict[str, Any]] = []
        for sid, codigo, intensidade, geom_json, ivc, iri, income_stress in raw:
            results.append({
                "id": sid,
                "codigo_setor": codigo,
                "nome": f"Setor {codigo[-4:]}",
                "intensidade_seguranca": round(intensidade, 3),
                "classe_intensidade": _classe(intensidade),
                "indice_vulnerabilidade": round(ivc, 2),
                "indice_risco_inundacao": round(iri, 2),
                "estresse_renda": round(income_stress, 2),
                "geom_json": geom_json,
            })
        return results

    @staticmethod
    def health_risk_points(db: Session, municipio_id: int) -> List[Dict[str, Any]]:
        from app.data_connectors.saude_collector import collect_saude_municipality

        muni = db.query(Municipio).filter(Municipio.id == municipio_id).first()
        if not muni:
            return []

        if db.query(EstabelecimentoSaude).filter(EstabelecimentoSaude.municipio_id == municipio_id).count() == 0:
            collect_saude_municipality(db, muni.codigo_ibge, force=True)

        vuln_setores = {
            item["id"]: item
            for item in AnalyticalEngine.calculate_climate_vulnerability_setores(db, municipio_id)
        }
        flood_setores = {
            item["id"]: item
            for item in AnalyticalEngine.calculate_flood_risk_setores(db, municipio_id)
        }
        high_ivc = max(
            (float(v.get("indice_vulnerabilidade", 0)) for v in vuln_setores.values()),
            default=0.5,
        )

        saude = db.query(MunicipioSaude).filter(MunicipioSaude.codigo_ibge == muni.codigo_ibge).first()
        saude_score = float(saude.cobertura_saude_score) if saude and saude.cobertura_saude_score is not None else 0.45

        points: list[dict[str, Any]] = []
        for est in db.query(EstabelecimentoSaude).filter(EstabelecimentoSaude.municipio_id == municipio_id).all():
            setor = (
                db.query(SetorCensitario)
                .filter(
                    SetorCensitario.municipio_id == municipio_id,
                    func.ST_DWithin(SetorCensitario.geom, est.geom, 0.03),
                )
                .order_by(func.ST_Distance(SetorCensitario.geom, est.geom))
                .first()
            )
            ivc = float(vuln_setores.get(setor.id, {}).get("indice_vulnerabilidade", 0.4)) if setor else 0.4
            iri = float(flood_setores.get(setor.id, {}).get("indice_risco_inundacao", 0.4)) if setor else 0.4
            bairro = (
                db.query(Bairro)
                .filter(Bairro.municipio_id == municipio_id, func.ST_DWithin(Bairro.geom, est.geom, 0.03))
                .order_by(func.ST_Distance(Bairro.geom, est.geom))
                .first()
            )
            bairro_nome = bairro.nome if bairro else (setor.codigo_setor if setor else "—")

            if est.tipo == "HOSPITAL" and int(est.leitos_sus or 0) >= 80:
                cobertura_classe = "ADEQUADA"
            elif ivc >= 0.62 and est.tipo in ("UBS", "CAPS") and iri >= 0.5:
                cobertura_classe = "CRITICA"
            elif ivc >= 0.55 or (iri >= 0.55 and est.tipo not in ("HOSPITAL", "SAMU")):
                cobertura_classe = "ATENCAO"
            elif saude_score >= 0.55 and ivc < 0.45:
                cobertura_classe = "ADEQUADA"
            else:
                cobertura_classe = "ATENCAO" if saude_score >= 0.35 else "CRITICA"

            dist_risco = round(max(0.0, (high_ivc - ivc) * 3 + iri * 2), 2)

            points.append({
                "id": est.id,
                "nome": est.nome,
                "tipo": est.tipo,
                "leitos_sus": est.leitos_sus,
                "bairro": bairro_nome,
                "cobertura_classe": cobertura_classe,
                "distancia_maior_risco_km": dist_risco,
                "indice_vulnerabilidade": round(ivc, 2),
                "indice_risco_inundacao": round(iri, 2),
                "geom_json": db.scalar(est.geom.ST_AsGeoJSON()),
                "feature_kind": "estabelecimento",
            })
        return points

    @staticmethod
    def health_risk_setores(db: Session, municipio_id: int) -> List[Dict[str, Any]]:
        """Pressão assistencial por setor — contexto espacial da cobertura."""
        muni = db.query(Municipio).filter(Municipio.id == municipio_id).first()
        if not muni:
            return []

        estabelecimentos = db.query(EstabelecimentoSaude).filter(
            EstabelecimentoSaude.municipio_id == municipio_id
        ).all()
        if not estabelecimentos:
            return []

        vuln_setores = {
            item["id"]: item
            for item in AnalyticalEngine.calculate_climate_vulnerability_setores(db, municipio_id)
        }
        flood_setores = {
            item["id"]: item
            for item in AnalyticalEngine.calculate_flood_risk_setores(db, municipio_id)
        }

        raw_pressures: list[tuple[int, float, str, str]] = []
        setores = db.query(SetorCensitario).filter(SetorCensitario.municipio_id == municipio_id).all()
        for setor in setores:
            ivc = float(vuln_setores.get(setor.id, {}).get("indice_vulnerabilidade", 0.4))
            iri = float(flood_setores.get(setor.id, {}).get("indice_risco_inundacao", 0.4))
            dist_deg = min(
                (db.scalar(func.ST_Distance(setor.geom, est.geom)) or 0.05 for est in estabelecimentos),
                default=0.05,
            )
            dist_km = float(dist_deg) * 111.0
            access_gap = min(1.0, dist_km / 4.0)
            pressure = min(1.0, (ivc * 0.38) + (iri * 0.32) + (access_gap * 0.30))
            raw_pressures.append((setor.id, pressure, setor.codigo_setor, db.scalar(setor.geom.ST_AsGeoJSON())))

        if len(raw_pressures) < 3:
            return []

        ordered = sorted(p for _, p, _, _ in raw_pressures)
        p33 = ordered[max(0, int(round((len(ordered) - 1) * 0.33)))]
        p66 = ordered[max(0, int(round((len(ordered) - 1) * 0.66)))]

        results: list[dict[str, Any]] = []
        for sid, pressure, codigo, geom_json in raw_pressures:
            if pressure >= p66:
                classe = "CRITICA"
            elif pressure <= p33:
                classe = "ADEQUADA"
            else:
                classe = "ATENCAO"
            results.append({
                "id": sid,
                "codigo_setor": codigo,
                "nome": f"Setor {codigo[-4:]}",
                "pressao_assistencial": round(pressure, 2),
                "cobertura_classe": classe,
                "geom_json": geom_json,
                "feature_kind": "setor_pressao",
            })
        return results
