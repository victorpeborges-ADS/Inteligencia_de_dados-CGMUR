import logging
from sqlalchemy.orm import Session
from app.db import SessionLocal, engine, Base
from app.models import CasoSucesso
from etl.etl_ibge import run_ibge_etl
from etl.etl_osm import run_osm_etl
from etl.etl_inmet import run_inmet_environmental_etl

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def seed_success_cases(db: Session):
    """
    Seeds the database with success cases of municipal adaptation and risk mitigation.
    """
    logger.info("Seeding municipal success cases...")
    db.query(CasoSucesso).delete()
    
    cases = [
        {
            "municipio": "Recife",
            "uf": "PE",
            "problema": "Deslizamento de encostas e risco geológico crítico nos morros habitados de alta densidade durante chuvas extremas de inverno.",
            "solucao": "Programa Parceria nos Morros. O município fornece materiais (cimento, ferro, geogrelhas) e assessoria técnica de engenharia, enquanto os próprios moradores realizam o trabalho comunitário (mutirão) para estabilizar encostas, construir canaletas de drenagem e aplicar revestimento protetor.",
            "resultado": "Mais de 1.500 encostas estabilizadas com baixíssimo custo por metro quadrado, engajamento comunitário ativo e redução de 80% nos incidentes fatais nas áreas cobertas pelo programa."
        },
        {
            "municipio": "Recife",
            "uf": "PE",
            "problema": "Efeito de ilha de calor urbana e degradação ambiental no entorno do Rio Capibaribe, cortando áreas altamente impermeabilizadas da capital.",
            "solucao": "Projeto Parque Capibaribe. Implementação de um corredor verde linear contínuo nas margens do rio Capibaribe, integrando ciclovias, caminhos de pedestres, arborização nativa e áreas de preservação permanente (APP).",
            "resultado": "Recuperação da mata ciliar urbana, redução local de até 2°C na temperatura superficial nos bairros adjacentes (como Jaqueira e Graças) e criação de espaços públicos resilientes à inundação."
        },
        {
            "municipio": "Salvador",
            "uf": "BA",
            "problema": "Elevado risco de grandes deslizamentos de terra nas encostas argilosas da cidade durante episódios de chuvas intensas e prolongadas.",
            "solucao": "Obras estruturantes de contenção de encostas com tecnologia de solo grampeado, cortinas atirantadas e aplicação de concreto projetado, integrando com sistemas de macro-drenagem e escadarias drenantes.",
            "resultado": "Mais de 100 grandes encostas de alto risco mitigadas de forma definitiva, eliminando a necessidade de evacuação emergencial sistemática em bairros periféricos."
        },
        {
            "municipio": "Curitiba",
            "uf": "PR",
            "problema": "Alagamentos recorrentes e inundações na bacia do Rio Belém e áreas centrais de baixa declividade devido ao aumento de asfalto.",
            "solucao": "Criação de parques inundáveis (como o Parque Barigui e Parque Tingui) que funcionam como bacias naturais de retenção temporária de cheias, associados a jardins de chuva urbanos e plantio massivo de espécies nativas.",
            "resultado": "Controle eficaz das inundações no centro urbano, recarga de aquíferos locais e valorização do solo no entorno com integração de áreas verdes de lazer."
        },
        {
            "municipio": "Belo Horizonte",
            "uf": "MG",
            "problema": "Inundações relâmpago catastróficas nas avenidas de fundo de vale (como Av. Vilarinho) decorrentes de temporais concentrados.",
            "solucao": "Construção de bacias de detenção subterrâneas gigantes (piscinões) integradas a sistemas inteligentes de monitoramento por telemetria e comportas automatizadas.",
            "resultado": "Retenção temporária de milhões de litros d'água de escoamento superficial, reduzindo a incidência de enchentes repentinas e perdas materiais nas avenidas críticas da capital mineira."
        }
    ]

    for c in cases:
        case_obj = CasoSucesso(
            municipio=c["municipio"],
            uf=c["uf"],
            problema=c["problema"],
            solucao=c["solucao"],
            resultado=c["resultado"]
        )
        db.add(case_obj)
    db.commit()
    logger.info("Success cases seeded successfully.")

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
