import json
import logging
from sqlalchemy.orm import Session
from sqlalchemy import func
from app.models import Municipio, Bairro, SetorCensitario, CoberturaVegetalMapBiomas, HistoricoDesastreS2ID, AlertaCemaden, InfraestruturaUrbana, MunicipioSaude, MunicipioSeguranca, MunicipioFiscal, EstabelecimentoSaude
from shapely.geometry import shape, mapping
from shapely.ops import unary_union
from typing import List, Dict, Any

logger = logging.getLogger(__name__)

class AnalyticalEngine:
    @staticmethod
    def _shape_from_db_geometry(db: Session, geom) -> Any:
        return shape(json.loads(db.scalar(geom.ST_AsGeoJSON())))

    @staticmethod
    def _covered_area_deg(db: Session, base_geom, cover_geoms) -> float:
        base_shape = AnalyticalEngine._shape_from_db_geometry(db, base_geom)
        cover_shapes = [
            AnalyticalEngine._shape_from_db_geometry(db, row.geom)
            for row in cover_geoms
        ]
        if not cover_shapes:
            return 0.0

        return base_shape.intersection(unary_union(cover_shapes)).area

    @staticmethod
    def calculate_climate_vulnerability(db: Session, municipio_id: int) -> List[Dict[str, Any]]:
        """
        Dynamically calculates the Climate Vulnerability Index (IVC) for all bairros
        in the municipality using PostGIS-driven aggregates.
        IVC = (Exposure + Sensitivity) - (Adaptive Capacity)
        All scores normalized between 0.0 and 1.0.
        """
        bairros = db.query(Bairro).filter(Bairro.municipio_id == municipio_id).all()
        results = []
        
        for b in bairros:
            # 1. Sensitivity: Population density & average income from sectors inside the Bairro
            # We use spatial intersection query
            sectors = db.query(SetorCensitario).filter(
                SetorCensitario.municipio_id == municipio_id,
                func.ST_Intersects(b.geom, SetorCensitario.geom)
            ).all()
            
            total_pop = sum(s.populacao for s in sectors)
            avg_income = sum(float(s.renda_media) for s in sectors) / len(sectors) if sectors else 1500.0
            
            # Neighborhood Area in km2 (ST_Area returns degrees for SRID 4326, we estimate based on centroid or convert)
            area_deg = db.scalar(func.ST_Area(b.geom))
            # Rough conversion factor for Recife lat (-8 deg): 1 sq degree = 12,300 km2
            area_km2 = float(area_deg) * 12300.0 if area_deg else 2.0
            
            density = total_pop / area_km2 if area_km2 > 0 else 0
            
            # Normalize density (cap at 15000 pop/km2)
            density_score = min(density / 15000.0, 1.0)
            # Normalize income (inverse: higher income = lower sensitivity. Cap at 7000 BRL)
            income_score = max(0.0, 1.0 - (avg_income / 7000.0))
            
            sensibilidade = (density_score * 0.5) + (income_score * 0.5)
            
            # 2. Exposure: Active Warnings (CEMADEN) & Historical Disasters (S2ID)
            # Count historical disasters in this neighborhood
            disasters_count = db.query(HistoricoDesastreS2ID).filter(
                func.ST_Intersects(b.geom, HistoricoDesastreS2ID.geom)
            ).count()
            
            # Check for active alerts intersecting
            active_alerts = db.query(AlertaCemaden).filter(
                func.ST_Intersects(b.geom, AlertaCemaden.geom)
            ).all()
            
            alert_weight = 0.0
            for alt in active_alerts:
                if alt.nivel_alerta == "MUITO_ALTO":
                    alert_weight = max(alert_weight, 1.0)
                elif alt.nivel_alerta == "ALTO":
                    alert_weight = max(alert_weight, 0.8)
                elif alt.nivel_alerta == "MEDIO":
                    alert_weight = max(alert_weight, 0.5)
                elif alt.nivel_alerta == "BAIXO":
                    alert_weight = max(alert_weight, 0.2)
                    
            disaster_score = min(disasters_count / 5.0, 1.0)
            exposicao = (disaster_score * 0.4) + (alert_weight * 0.6)
            
            # 3. Adaptive Capacity: Vegetation coverage % + Healthcare infrastructure count
            # Calculate total vegetation cover inside neighborhood
            forest_cover = db.query(CoberturaVegetalMapBiomas).filter(
                CoberturaVegetalMapBiomas.municipio_id == municipio_id,
                CoberturaVegetalMapBiomas.classe_uso == "Vegetação / Floresta",
                func.ST_Intersects(b.geom, CoberturaVegetalMapBiomas.geom)
            ).all()
            veg_area_deg = AnalyticalEngine._covered_area_deg(db, b.geom, forest_cover)
            
            # If subquery union is empty, fallback to simple calculations or standard values
            veg_pct = 0.0
            if veg_area_deg and area_deg:
                veg_pct = float(veg_area_deg) / float(area_deg)
                
            # Hospitals count inside the neighborhood
            hospitals_count = db.query(InfraestruturaUrbana).filter(
                InfraestruturaUrbana.tipo == "hospital",
                func.ST_Intersects(b.geom, InfraestruturaUrbana.geom)
            ).count()
            
            veg_score = min(veg_pct * 3.0, 1.0) # 33% vegetation = full score
            infra_score = min(hospitals_count / 2.0, 1.0) # 2 hospitals = full score
            
            capacidade_adaptacao = (veg_score * 0.6) + (infra_score * 0.4)
            
            # Final Climate Vulnerability Index (IVC)
            # IVC = (exposicao + sensibilidade) / 2 adjusted by (1 - capacidade)
            ivc = (exposicao + sensibilidade) / 2.0
            ivc = ivc * (1.0 - (capacidade_adaptacao * 0.3)) # Adaptive capacity reduces vulnerability by up to 30%
            ivc = round(max(0.0, min(1.0, ivc)), 2)
            
            results.append({
                "id": b.id,
                "bairro_nome": b.nome,
                "exposicao": round(exposicao, 2),
                "sensibilidade": round(sensibilidade, 2),
                "capacidade_adaptacao": round(capacidade_adaptacao, 2),
                "indice_vulnerabilidade": ivc
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
        
        for b in bairros:
            # 1. Historical S2ID Flood events
            flood_disasters = db.query(HistoricoDesastreS2ID).filter(
                HistoricoDesastreS2ID.tipo_desastre.in_(["Inundação", "Alagamento Urbano"]),
                func.ST_Intersects(b.geom, HistoricoDesastreS2ID.geom)
            ).count()
            s2id_score = min(flood_disasters / 3.0, 1.0) # 3 floods = max score
            
            # 2. Impervious surface cover (simulated from Urban Class % in MapBiomas)
            area_deg = db.scalar(func.ST_Area(b.geom))
            
            urban_cover = db.query(CoberturaVegetalMapBiomas).filter(
                CoberturaVegetalMapBiomas.municipio_id == municipio_id,
                CoberturaVegetalMapBiomas.classe_uso == "Área Urbana",
                func.ST_Intersects(b.geom, CoberturaVegetalMapBiomas.geom)
            ).all()
            urban_area_deg = AnalyticalEngine._covered_area_deg(db, b.geom, urban_cover)
            
            urban_pct = 0.5 # default fallback
            if urban_area_deg and area_deg:
                urban_pct = float(urban_area_deg) / float(area_deg)
                
            impermeabilizacao_score = min(urban_pct, 1.0)
            
            # 3. Proximity to Capibaribe / Beberibe water bodies
            # (Calculated by check if Water Class intersects)
            has_water = db.query(CoberturaVegetalMapBiomas).filter(
                CoberturaVegetalMapBiomas.municipio_id == municipio_id,
                CoberturaVegetalMapBiomas.classe_uso == "Corpo d'água",
                func.ST_Intersects(b.geom, CoberturaVegetalMapBiomas.geom)
            ).first() is not None
            
            water_score = 1.0 if has_water else 0.2
            
            # Compound Index calculation
            iri = (s2id_score * 0.4) + (impermeabilizacao_score * 0.4) + (water_score * 0.2)
            iri = round(max(0.0, min(1.0, iri)), 2)
            
            results.append({
                "id": b.id,
                "bairro_nome": b.nome,
                "s2id_historico_score": round(s2id_score, 2),
                "impermeabilizacao_score": round(impermeabilizacao_score, 2),
                "hidrografia_proximidade_score": round(water_score, 2),
                "indice_risco_inundacao": iri
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
    ) -> tuple[list[str], int]:
        """Calcula bairros e população expostos a partir da geometria final de risco."""
        affected_bairros: list[str] = []
        affected_pop = 0

        for b in bairros:
            b_geom = shape(json.loads(db.scalar(b.geom.ST_AsGeoJSON())))
            intersect = b_geom.intersection(hazard_geom)
            if intersect.is_empty:
                continue

            affected_bairros.append(b.nome)
            ratio = intersect.area / b_geom.area if b_geom.area > 0 else 0
            sectors = db.query(SetorCensitario).filter(
                SetorCensitario.municipio_id == muni_id,
                func.ST_Intersects(b.geom, SetorCensitario.geom),
            ).all()
            b_pop = sum(s.populacao for s in sectors)
            affected_pop += int(b_pop * ratio * intensity_factor)

        cap = muni.populacao or affected_pop
        return affected_bairros, min(affected_pop, cap)

    @staticmethod
    def run_chuva_extrema_simulation(db: Session, muni_id: int, precipitacao_mm: float) -> Dict[str, Any]:
        """
        Simula chuva extrema com DEM SRTM, IRI por bairro, deslizamento por declividade
        e métricas recalculadas após união das manchas finais.
        """
        from app.services.hydro_simulator import enrich_rainfall_simulation

        muni = db.query(Municipio).filter(Municipio.id == muni_id).first()
        bairros = db.query(Bairro).filter(Bairro.municipio_id == muni_id).all()
        muni_shape = shape(json.loads(db.scalar(muni.geom.ST_AsGeoJSON())))

        terrain = enrich_rainfall_simulation(db, muni, precipitacao_mm)
        flood_bands = terrain.get("flood_bands")
        intensity = 1.2 + (precipitacao_mm / 100.0)

        if flood_bands and flood_bands.get("features"):
            hazard_shapes = [
                shape(f["geometry"]) for f in flood_bands["features"]
            ]
            final_hazards = unary_union(hazard_shapes).intersection(muni_shape)
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

        affected_bairros, affected_pop = AnalyticalEngine._impact_from_hazard(
            db, muni_id, muni, bairros, final_hazards, intensity_factor=intensity,
        )

        return {
            "scenario_type": "ExtremeRainfall",
            "input_value": precipitacao_mm,
            "metric_impact": "População em áreas de alto risco de desastre",
            "impact_value": affected_pop,
            "affected_area_km2": round(final_hazards.area * 12300.0, 2),
            "affected_population": affected_pop,
            "affected_bairros": affected_bairros,
            "geometry": fc,
            "contours": terrain.get("contours"),
            "flow_paths": terrain.get("flow_paths"),
            "simulation_meta": terrain.get("simulation_meta"),
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
    def health_risk_points(db: Session, municipio_id: int) -> List[Dict[str, Any]]:
        muni = db.query(Municipio).filter(Municipio.id == municipio_id).first()
        vuln = {v["bairro_nome"]: v for v in AnalyticalEngine.calculate_climate_vulnerability(db, municipio_id)}
        high = max(vuln.values(), key=lambda x: x["indice_vulnerabilidade"], default={"indice_vulnerabilidade": 0.5, "bairro_nome": ""})
        high_name = high.get("bairro_nome")
        saude = db.query(MunicipioSaude).filter(MunicipioSaude.codigo_ibge == muni.codigo_ibge).first()
        saude_score = float(saude.cobertura_saude_score) if saude and saude.cobertura_saude_score is not None else 0.45

        points = []
        for est in db.query(EstabelecimentoSaude).filter(EstabelecimentoSaude.municipio_id == municipio_id).all():
            bairro_prox = db.query(Bairro).filter(
                Bairro.municipio_id == municipio_id,
                func.ST_DWithin(Bairro.geom, est.geom, 0.02),
            ).order_by(func.ST_Distance(Bairro.geom, est.geom)).first()
            bairro_nome = bairro_prox.nome if bairro_prox else "—"
            ivc = float(vuln.get(bairro_nome, {}).get("indice_vulnerabilidade", 0.4))
            cobertura_classe = "ADEQUADA" if saude_score >= 0.6 and ivc < 0.5 else ("ATENCAO" if saude_score >= 0.35 else "CRITICA")
            if ivc >= 0.65 and saude_score < 0.45:
                cobertura_classe = "CRITICA"

            dist_risco = 0.0 if bairro_nome == high_name else round(ivc * 5, 2)

            points.append({
                "id": est.id,
                "nome": est.nome,
                "tipo": est.tipo,
                "leitos_sus": est.leitos_sus,
                "bairro": bairro_nome,
                "cobertura_classe": cobertura_classe,
                "distancia_maior_risco_km": dist_risco,
                "geom_json": db.scalar(est.geom.ST_AsGeoJSON()),
            })
        return points
