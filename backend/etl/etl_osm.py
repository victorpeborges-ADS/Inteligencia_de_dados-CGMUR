import requests
import logging
from sqlalchemy.orm import Session
from shapely.geometry import Point, LineString
from app.models import InfraestruturaUrbana, Municipio

logger = logging.getLogger(__name__)

# Bounding box for Recife
RECIFE_BBOX = "-8.16,-34.98,-7.94,-34.85"

def query_overpass_api(query_type: str):
    """
    Queries OSM Overpass API. Returns GeoJSON elements or None.
    """
    overpass_url = "https://overpass-api.de/api/interpreter"
    
    if query_type == "hospitals":
        osm_query = f"""
        [out:json][timeout:10];
        (
          node["amenity"="hospital"]({RECIFE_BBOX});
          way["amenity"="hospital"]({RECIFE_BBOX});
        );
        out body geom;
        """
    elif query_type == "schools":
        osm_query = f"""
        [out:json][timeout:10];
        (
          node["amenity"="school"]({RECIFE_BBOX});
          way["amenity"="school"]({RECIFE_BBOX});
        );
        out body geom;
        """
    elif query_type == "roads":
        osm_query = f"""
        [out:json][timeout:10];
        (
          way["highway"~"primary|secondary"]({RECIFE_BBOX});
        );
        out body geom;
        """
    else:
        return None

    try:
        logger.info(f"Querying Overpass for {query_type}...")
        response = requests.post(overpass_url, data={'data': osm_query}, timeout=12)
        if response.status_code == 200:
            return response.json().get("elements", [])
    except Exception as e:
        logger.error(f"Overpass query for {query_type} failed: {e}")
    return []

def load_simulated_infrastructure(db: Session, muni_id: int):
    """
    Fallback loader to generate real, recognizable Recife entities 
    when Overpass is unavailable.
    """
    logger.info("Using fallback mechanism to seed realistic Recife urban infrastructure.")
    
    # 1. Hospitals (Points)
    hospitals = [
        {"nome": "Real Hospital Português", "sub": "hospital_particular", "lat": -8.0664, "lng": -34.8992},
        {"nome": "Hospital da Restauração", "sub": "hospital_publico_urgencia", "lat": -8.0592, "lng": -34.8981},
        {"nome": "Hospital das Clínicas UFPE", "sub": "hospital_publico_universitario", "lat": -8.0487, "lng": -34.9431},
        {"nome": "IMIP - Instituto de Medicina Integral Professor Fernando Figueira", "sub": "hospital_filantropico", "lat": -8.0729, "lng": -34.8931},
        {"nome": "Hospital Jayme da Fonte", "sub": "hospital_particular", "lat": -8.0469, "lng": -34.8878},
        {"nome": "UPA Imbiribeira", "sub": "pronto_atendimento", "lat": -8.1132, "lng": -34.9084},
        {"nome": "Hospital Esperança Recife", "sub": "hospital_particular", "lat": -8.0641, "lng": -34.8953},
        {"nome": "Hospital Getúlio Vargas", "sub": "hospital_publico", "lat": -8.0652, "lng": -34.9208}
    ]
    
    for h in hospitals:
        pt = Point(h["lng"], h["lat"])
        infra = InfraestruturaUrbana(
            municipio_id=muni_id,
            tipo="hospital",
            nome=h["nome"],
            subgrupo=h["sub"],
            geom=f"SRID=4326;{pt.wkt}"
        )
        db.add(infra)
        
    # 2. Schools (Points)
    schools = [
        {"nome": "Colégio Militar do Recife", "sub": "escola_federal", "lat": -8.0475, "lng": -34.9077},
        {"nome": "Colégio Damas da Instrução Cristã", "sub": "escola_privada", "lat": -8.0372, "lng": -34.9038},
        {"nome": "Ginásio Pernambucano (Cabugá)", "sub": "escola_estadual", "lat": -8.0531, "lng": -34.8806},
        {"nome": "Escola Técnica Estadual Cícero Dias", "sub": "escola_tecnica", "lat": -8.1215, "lng": -34.9042},
        {"nome": "Colégio de Aplicação da UFPE", "sub": "escola_federal", "lat": -8.0494, "lng": -34.9452},
        {"nome": "Colégio Santa Maria", "sub": "escola_privada", "lat": -8.1251, "lng": -34.9009},
        {"nome": "Escola Estadual Sizenando Silveira", "sub": "escola_estadual", "lat": -8.0578, "lng": -34.8885}
    ]
    
    for s in schools:
        pt = Point(s["lng"], s["lat"])
        infra = InfraestruturaUrbana(
            municipio_id=muni_id,
            tipo="escola",
            nome=s["nome"],
            subgrupo=s["sub"],
            geom=f"SRID=4326;{pt.wkt}"
        )
        db.add(infra)

    # 3. Major Roads (LineStrings)
    roads = [
        {
            "nome": "Avenida Agamenon Magalhães", "sub": "via_arterial",
            "coords": [[-34.8988, -8.0712], [-34.8943, -8.0575], [-34.8892, -8.0441], [-34.8837, -8.0264]]
        },
        {
            "nome": "Avenida Norte Miguel Arraes de Alencar", "sub": "via_arterial",
            "coords": [[-34.8781, -8.0504], [-34.8911, -8.0412], [-34.9056, -8.0305], [-34.9288, -8.0162]]
        },
        {
            "nome": "Avenida Boa Viagem", "sub": "via_coletora",
            "coords": [[-34.8814, -8.0831], [-34.8988, -8.1189], [-34.9022, -8.1362], [-34.9082, -8.1524]]
        },
        {
            "nome": "Avenida Caxangá", "sub": "via_arterial",
            "coords": [[-34.9099, -8.0628], [-34.9254, -8.0567], [-34.9452, -8.0487], [-34.9691, -8.0381]]
        },
        {
            "nome": "Avenida Mascarenhas de Morais", "sub": "via_arterial",
            "coords": [[-34.9082, -8.0934], [-34.9094, -8.1154], [-34.9142, -8.1381], [-34.9212, -8.1598]]
        }
    ]

    for r in roads:
        ls = LineString(r["coords"])
        infra = InfraestruturaUrbana(
            municipio_id=muni_id,
            tipo="via",
            nome=r["nome"],
            subgrupo=r["sub"],
            geom=f"SRID=4326;{ls.wkt}"
        )
        db.add(infra)
        
    db.commit()


def load_simulated_roads_only(db: Session, muni_id: int) -> int:
    """Insere só vias arteriais do Recife (não apaga equipamentos)."""
    roads = [
        {
            "nome": "Avenida Agamenon Magalhães", "sub": "via_arterial",
            "coords": [[-34.8988, -8.0712], [-34.8943, -8.0575], [-34.8892, -8.0441], [-34.8837, -8.0264]]
        },
        {
            "nome": "Avenida Norte Miguel Arraes de Alencar", "sub": "via_arterial",
            "coords": [[-34.8781, -8.0504], [-34.8911, -8.0412], [-34.9056, -8.0305], [-34.9288, -8.0162]]
        },
        {
            "nome": "Avenida Boa Viagem", "sub": "via_coletora",
            "coords": [[-34.8814, -8.0831], [-34.8988, -8.1189], [-34.9022, -8.1362], [-34.9082, -8.1524]]
        },
        {
            "nome": "Avenida Caxangá", "sub": "via_arterial",
            "coords": [[-34.9099, -8.0628], [-34.9254, -8.0567], [-34.9452, -8.0487], [-34.9691, -8.0381]]
        },
        {
            "nome": "Avenida Mascarenhas de Morais", "sub": "via_arterial",
            "coords": [[-34.9082, -8.0934], [-34.9094, -8.1154], [-34.9142, -8.1381], [-34.9212, -8.1598]]
        },
    ]
    n = 0
    for r in roads:
        ls = LineString(r["coords"])
        db.add(
            InfraestruturaUrbana(
                municipio_id=muni_id,
                tipo="via",
                nome=r["nome"],
                subgrupo=r["sub"],
                geom=f"SRID=4326;{ls.wkt}",
            )
        )
        n += 1
    return n

def run_osm_etl(db: Session, muni_id: int):
    logger.info("Starting OpenStreetMap ETL pipeline...")
    db.query(InfraestruturaUrbana).filter(InfraestruturaUrbana.municipio_id == muni_id).delete()
    
    # Query OSM
    hospitals = query_overpass_api("hospitals")
    schools = query_overpass_api("schools")
    roads = query_overpass_api("roads")
    
    # If no data found or request timed out, load fallback simulated data
    if not hospitals and not schools and not roads:
        load_simulated_infrastructure(db, muni_id)
        logger.info("Loaded simulated infrastructure data (OSM fallback).")
        return
        
    # Process OSM Hospitals
    loaded_items = 0
    for h in hospitals:
        name = h.get("tags", {}).get("name", "Hospital Sem Nome")
        sub = h.get("tags", {}).get("healthcare", "hospital")
        lat = h.get("lat")
        lon = h.get("lon")
        
        # In case it is a way, get center
        if not lat and "bounds" in h:
            lat = (h["bounds"]["minlat"] + h["bounds"]["maxlat"]) / 2
            lon = (h["bounds"]["minlon"] + h["bounds"]["maxlon"]) / 2
            
        if lat and lon:
            pt = Point(lon, lat)
            infra = InfraestruturaUrbana(
                municipio_id=muni_id,
                tipo="hospital",
                nome=name,
                subgrupo=sub,
                geom=f"SRID=4326;{pt.wkt}"
            )
            db.add(infra)
            loaded_items += 1
            
    # Process OSM Schools
    for s in schools:
        name = s.get("tags", {}).get("name", "Escola Sem Nome")
        sub = s.get("tags", {}).get("school:type", "escola")
        lat = s.get("lat")
        lon = s.get("lon")
        
        if not lat and "bounds" in s:
            lat = (s["bounds"]["minlat"] + s["bounds"]["maxlat"]) / 2
            lon = (s["bounds"]["minlon"] + s["bounds"]["maxlon"]) / 2
            
        if lat and lon:
            pt = Point(lon, lat)
            infra = InfraestruturaUrbana(
                municipio_id=muni_id,
                tipo="escola",
                nome=name,
                subgrupo=sub,
                geom=f"SRID=4326;{pt.wkt}"
            )
            db.add(infra)
            loaded_items += 1

    # Process OSM Roads
    for r in roads:
        name = r.get("tags", {}).get("name", "Via Sem Nome")
        sub = r.get("tags", {}).get("highway", "secundaria")
        geometry = r.get("geometry", [])
        
        if len(geometry) >= 2:
            coords = [[pt["lon"], pt["lat"]] for pt in geometry]
            ls = LineString(coords)
            infra = InfraestruturaUrbana(
                municipio_id=muni_id,
                tipo="via",
                nome=name,
                subgrupo=sub,
                geom=f"SRID=4326;{ls.wkt}"
            )
            db.add(infra)
            loaded_items += 1

    db.commit()
    logger.info(f"Loaded {loaded_items} OSM items directly from Overpass API.")
