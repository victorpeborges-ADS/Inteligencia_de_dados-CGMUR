import logging
from sqlalchemy.orm import Session
from app.db import SessionLocal, engine, Base
from etl.etl_ibge import run_ibge_etl
from etl.etl_osm import run_osm_etl
from etl.etl_inmet import run_inmet_environmental_etl

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def seed_success_cases(db: Session):
    """Delega ao serviço central de casos de sucesso."""
    from app.services.casos_sucesso_service import seed_casos_sucesso

    return seed_casos_sucesso(db, force=True, embed=True)

def run_all_etl():
    logger.info("--- Starting SINIDU Master ETL Orchestration ---")
    db = SessionLocal()
    try:
        # Step 1: Boundaries, Neighborhoods & Sectors (IBGE)
        muni_id = run_ibge_etl(db)
        
        # Step 2: Infrastructure (OSM)
        run_osm_etl(db, muni_id)
        
        # Step 3: Environmental Layers (INMET, MapBiomas, S2ID, CEMADEN)
        run_inmet_environmental_etl(db, muni_id)
        
        # Step 4: Success Cases Database
        seed_success_cases(db)
        
        logger.info("--- ETL Orchestration Completed Successfully! ---")
    except Exception as e:
        logger.error(f"ETL Orchestration failed: {e}", exc_info=True)
    finally:
        db.close()

if __name__ == "__main__":
    # Ensure tables exist
    Base.metadata.create_all(bind=engine)
    run_all_etl()
