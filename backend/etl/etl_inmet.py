import datetime
import logging
from sqlalchemy.orm import Session
from shapely.geometry import Point, Polygon, MultiPolygon, shape
from app.models import HistoricoDesastreS2ID, AlertaCemaden, CoberturaVegetalMapBiomas, Bairro

logger = logging.getLogger(__name__)

def run_inmet_environmental_etl(db: Session, muni_id: int):
    logger.info("Starting INMET & Environmental Data ETL pipeline...")
    
    # 1. Clear existing data
    db.query(HistoricoDesastreS2ID).filter(HistoricoDesastreS2ID.municipio_id == muni_id).delete()
    db.query(AlertaCemaden).filter(AlertaCemaden.municipio_id == muni_id).delete()
    db.query(CoberturaVegetalMapBiomas).filter(CoberturaVegetalMapBiomas.municipio_id == muni_id).delete()
    db.commit()

    # 2. Seed Historical S2ID Disasters
    # Let's seed major events in Recife:
    # May 2022 Landslide in Ibura
    # June 2023 Flooding in Centro / Agamenon
    desastres = [
        {
            "tipo": "Deslizamento de Terra",
            "data": datetime.date(2022, 5, 28),
            "afetados": 12000,
            "danos": 45000000.00,
            "lat": -8.1368, "lng": -34.9587  # Ibura Hills
        },
        {
            "tipo": "Inundação",
            "data": datetime.date(2023, 6, 15),
            "afetados": 8000,
            "danos": 15000000.00,
            "lat": -8.0583, "lng": -34.8972  # Agamenon Magalhães/Espinheiro
        },
        {
            "tipo": "Alagamento Urbano",
            "data": datetime.date(2024, 5, 10),
            "afetados": 3500,
            "danos": 5000000.00,
            "lat": -8.0621, "lng": -34.8732  # Centro / Bairro do Recife
        },
        {
            "tipo": "Deslizamento de Terra",
            "data": datetime.date(2024, 5, 11),
            "afetados": 1500,
            "danos": 2500000.00,
            "lat": -8.0182, "lng": -34.9124  # Córrego do Jenipapo / Arruda hills
        }
    ]

    for d in desastres:
        pt = Point(d["lng"], d["lat"])
        des_obj = HistoricoDesastreS2ID(
            municipio_id=muni_id,
            tipo_desastre=d["tipo"],
            data_ocorrencia=d["data"],
            populacao_afetada=d["afetados"],
            danos_materiais=d["danos"],
            geom=f"SRID=4326;{pt.wkt}"
        )
        db.add(des_obj)

    # 3. Seed Active CEMADEN Alerts
    # We will generate alert polygons covering the hills (Ibura, Arruda/Casa Amarela)
    # Ibura hills polygon
    ibura_alert_poly = Polygon([
        [-34.965, -8.145],
        [-34.950, -8.145],
        [-34.950, -8.130],
        [-34.965, -8.130],
        [-34.965, -8.145]
    ])
    
    # Arruda hills polygon
    arruda_alert_poly = Polygon([
        [-34.920, -8.020],
        [-34.905, -8.020],
        [-34.905, -8.010],
        [-34.920, -8.010],
        [-34.920, -8.020]
    ])

    alerts = [
        {
            "nivel": "MUITO_ALTO",
            "desc": "Risco muito alto de movimentos de massa (deslizamentos) devido a acumulado pluviométrico crítico nas últimas 72h nos morros do Ibura.",
            "geom": MultiPolygon([ibura_alert_poly])
        },
        {
            "nivel": "MEDIO",
            "desc": "Risco moderado de alagamentos e deslizamentos localizados na zona norte (Córrego do Jenipapo / Vasco da Gama / Arruda).",
            "geom": MultiPolygon([arruda_alert_poly])
        }
    ]

    for a in alerts:
        alt_obj = AlertaCemaden(
            municipio_id=muni_id,
            nivel_alerta=a["nivel"],
            data_alerta=datetime.datetime.utcnow(),
            descricao=a["desc"],
            geom=f"SRID=4326;{a['geom'].wkt}"
        )
        db.add(alt_obj)

    # 4. Seed MapBiomas Land Use Cover (MapBiomas)
    # We query the neighborhood boundaries from the database and intersect them
    # to create representative vegetation cover polygons for "Floresta", "Área Urbana", "Água".
    # This simulates MapBiomas raster-to-vector aggregation.
    
    bairros = db.query(Bairro).filter(Bairro.municipio_id == muni_id).all()
    
    for b in bairros:
        # Load neighborhood geometry from database
        import json
        b_geom_dict = json.loads(db.scalar(b.geom.ST_AsGeoJSON()))
        b_shape = shape(b_geom_dict)
        
        # Subdivide neighborhood geometry into land cover zones
        # We split the neighborhood bounding box in half: 
        # Left half = Forest or Urban, Right half = Urban or Water.
        min_x, min_y, max_x, max_y = b_shape.bounds
        mid_x = (min_x + max_x) / 2
        
        poly_left = Polygon([[min_x, min_y], [mid_x, min_y], [mid_x, max_y], [min_x, max_y], [min_x, min_y]])
        poly_right = Polygon([[mid_x, min_y], [max_x, min_y], [max_x, max_y], [mid_x, max_y], [mid_x, min_y]])
        
        geom_left = b_shape.intersection(poly_left)
        geom_right = b_shape.intersection(poly_right)
        
        # Set classes based on neighborhood name
        if b.nome in ["Boa Viagem", "Centro", "Santo Amaro", "Arruda"]:
            class_left = "Área Urbana"
            class_right = "Corpo d'água" if b.nome in ["Boa Viagem", "Centro"] else "Área Urbana"
        elif b.nome in ["Apipucos", "Casa Forte", "Várzea"]:
            class_left = "Vegetação / Floresta"
            class_right = "Área Urbana"
        else: # Ibura, Afogados, Madalena
            class_left = "Área Urbana"
            class_right = "Vegetação / Floresta"

        # Save left geometry if valid
        if not geom_left.is_empty:
            if isinstance(geom_left, Polygon):
                geom_left = MultiPolygon([geom_left])
            if isinstance(geom_left, MultiPolygon):
                veg_left = CoberturaVegetalMapBiomas(
                    municipio_id=muni_id,
                    ano=2024,
                    classe_uso=class_left,
                    geom=f"SRID=4326;{geom_left.wkt}"
                )
                db.add(veg_left)

        # Save right geometry if valid
        if not geom_right.is_empty:
            if isinstance(geom_right, Polygon):
                geom_right = MultiPolygon([geom_right])
            if isinstance(geom_right, MultiPolygon):
                veg_right = CoberturaVegetalMapBiomas(
                    municipio_id=muni_id,
                    ano=2024,
                    classe_uso=class_right,
                    geom=f"SRID=4326;{geom_right.wkt}"
                )
                db.add(veg_right)

    db.commit()
    logger.info("Successfully loaded environmental and weather-related layers.")
