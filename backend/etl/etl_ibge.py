import requests
import json
import logging
from sqlalchemy.orm import Session
from shapely.geometry import shape, MultiPolygon, Polygon
from shapely.ops import unary_union
from app.models import Municipio, Bairro, SetorCensitario
from app.config import settings

logger = logging.getLogger(__name__)

def fetch_recife_boundary():
    """
    Fetches the official Recife municipal boundary from IBGE Web Service.
    Falls back to a standard bounding box polygon if the API is offline.
    """
    ibge_code = settings.PILOT_IBGE_CODE
    url = f"https://servicodados.ibge.gov.br/api/v3/malhas/municipios/{ibge_code}?qualidade=minima&formato=application/vnd.geo+json"
    
    try:
        logger.info(f"Fetching Recife boundary from IBGE API: {url}")
        response = requests.get(url, timeout=15)
        if response.status_code == 200:
            geojson = response.json()
            if "features" in geojson and len(geojson["features"]) > 0:
                feat = geojson["features"][0]
                geom_data = feat["geometry"]
                # Convert to shapely shape
                sh_geom = shape(geom_data)
                if isinstance(sh_geom, Polygon):
                    sh_geom = MultiPolygon([sh_geom])
                return sh_geom
    except Exception as e:
        logger.error(f"Error fetching IBGE boundary: {e}. Falling back to default polygon.")
    
    # Bounding Box fallback for Recife
    # MinLng: -34.98, MinLat: -8.16, MaxLng: -34.85, MaxLat: -7.94
    coords = [
        [-34.97, -8.15],
        [-34.85, -8.13],
        [-34.86, -7.95],
        [-34.96, -7.94],
        [-34.97, -8.15]
    ]
    return MultiPolygon([Polygon(coords)])

def partition_municipality_into_bairros(muni_geom: MultiPolygon):
    """
    Subdivides the municipal boundary into 10 major neighborhoods (bairros)
    for Recife, representing administrative zones with coordinates and typical characteristics.
    """
    min_x, min_y, max_x, max_y = muni_geom.bounds
    dx = (max_x - min_x) / 4
    dy = (max_y - min_y) / 3
    
    # Grid of polygons to cut the municipality
    grid_polys = []
    for i in range(4):
        for j in range(3):
            gx1 = min_x + i * dx
            gy1 = min_y + j * dy
            gx2 = gx1 + dx
            gy2 = gy1 + dy
            grid_polys.append(Polygon([[gx1, gy1], [gx2, gy1], [gx2, gy2], [gx1, gy2], [gx1, gy1]]))
            
    bairro_configs = [
        {"nome": "Boa Viagem", "income_level": "alto", "pop_density": "alta"},
        {"nome": "Ibura", "income_level": "baixo", "pop_density": "alta"},
        {"nome": "Várzea", "income_level": "medio", "pop_density": "media"},
        {"nome": "Centro", "income_level": "medio", "pop_density": "baixa"},
        {"nome": "Casa Forte", "income_level": "alto", "pop_density": "media"},
        {"nome": "Madalena", "income_level": "alto", "pop_density": "alta"},
        {"nome": "Santo Amaro", "income_level": "baixo", "pop_density": "alta"},
        {"nome": "Arruda", "income_level": "baixo", "pop_density": "alta"},
        {"nome": "Apipucos", "income_level": "alto", "pop_density": "baixa"},
        {"nome": "Afogados", "income_level": "baixo", "pop_density": "media"}
    ]
    
    bairros_data = []
    # Intersection grid cells with municipal boundary to get actual neighborhood shapes
    idx = 0
    for cell in grid_polys:
        intersect = muni_geom.intersection(cell)
        if not intersect.is_empty:
            if isinstance(intersect, Polygon):
                intersect = MultiPolygon([intersect])
            
            # Map to config
            cfg = bairro_configs[idx % len(bairro_configs)]
            bairros_data.append({
                "nome": cfg["nome"],
                "income_level": cfg["income_level"],
                "pop_density": cfg["pop_density"],
                "geom": intersect
            })
            idx += 1
            
    return bairros_data

def run_ibge_etl(db: Session):
    logger.info("Starting IBGE ETL pipeline...")
    
    # 1. Load Municipio
    db.query(Municipio).delete()
    muni_geom = fetch_recife_boundary()
    
    muni = Municipio(
        codigo_ibge=settings.PILOT_IBGE_CODE,
        nome=settings.PILOT_NAME,
        uf=settings.PILOT_UF,
        populacao=1488920,
        area_km2=218.4,
        geom=f"SRID=4326;{muni_geom.wkt}"
    )
    db.add(muni)
    db.commit()
    db.refresh(muni)
    logger.info(f"Loaded municipality: {muni.nome} - {muni.uf} ({muni.id})")
    
    # 2. Partition into Bairros
    db.query(Bairro).delete()
    bairros = partition_municipality_into_bairros(muni_geom)
    
    for idx, b in enumerate(bairros):
        bairro_obj = Bairro(
            municipio_id=muni.id,
            nome=b["nome"],
            codigo_bairro=f"2611606{idx+1:02d}",
            geom=f"SRID=4326;{b['geom'].wkt}"
        )
        db.add(bairro_obj)
    db.commit()
    logger.info(f"Loaded {len(bairros)} neighborhoods (bairros) for {muni.nome}")
    
    # 3. Create Setores Censitários (Census Sectors) within Bairros
    db.query(SetorCensitario).delete()
    
    # Fetch bairros we just saved
    saved_bairros = db.query(Bairro).filter(Bairro.municipio_id == muni.id).all()
    
    sector_count = 0
    for b in saved_bairros:
        # Determine income/density defaults based on neighborhood configuration
        # Let's map back to name
        b_name = b.nome
        if b_name in ["Boa Viagem", "Casa Forte", "Apipucos", "Madalena"]:
            income_base = 6500.00
            pop_base = 120
        elif b_name in ["Ibura", "Santo Amaro", "Arruda", "Afogados"]:
            income_base = 1412.00  # Minimum wage (approximate for base year)
            pop_base = 350
        else:
            income_base = 2800.00
            pop_base = 200

        # Subdivide each neighborhood into 4 sectors
        b_geom = shape(json.loads(db.scalar(b.geom.ST_AsGeoJSON())))
        min_x, min_y, max_x, max_y = b_geom.bounds
        dx = (max_x - min_x) / 2
        dy = (max_y - min_y) / 2
        
        for i in range(2):
            for j in range(2):
                gx1 = min_x + i * dx
                gy1 = min_y + j * dy
                gx2 = gx1 + dx
                gy2 = gy1 + dy
                cell = Polygon([[gx1, gy1], [gx2, gy1], [gx2, gy2], [gx1, gy2], [gx1, gy1]])
                sec_geom = b_geom.intersection(cell)
                if not sec_geom.is_empty:
                    if isinstance(sec_geom, Polygon):
                        sec_geom = MultiPolygon([sec_geom])
                    elif not isinstance(sec_geom, MultiPolygon):
                        continue
                        
                    sector_count += 1
                    # Add some randomness to income and population
                    income = income_base * (0.8 + (sector_count % 5) * 0.1)
                    pop = int(pop_base * (0.9 + (sector_count % 3) * 0.15))
                    
                    sec_obj = SetorCensitario(
                        municipio_id=muni.id,
                        codigo_setor=f"2611606{b.id:02d}{sector_count:03d}",
                        populacao=pop,
                        renda_media=income,
                        geom=f"SRID=4326;{sec_geom.wkt}"
                    )
                    db.add(sec_obj)
                    
    db.commit()
    logger.info(f"Loaded {sector_count} sectors (setores censitários) for {muni.nome}")
    return muni.id
