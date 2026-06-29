import datetime
import requests
from sqlalchemy.orm import Session
from shapely.geometry import MultiPolygon, Point, Polygon, LineString
from app.models import (
    Municipio,
    Bairro,
    SetorCensitario,
    HistoricoDesastreS2ID,
    AlertaCemaden,
    CoberturaVegetalMapBiomas,
    InfraestruturaUrbana,
)


DEMO_MUNICIPIOS = [
    {
        "codigo_ibge": "1400233",
        "nome": "Caroebe",
        "uf": "RR",
        "populacao": 11400,
        "area_km2": 12066.2,
        "bbox": [-60.92, 0.62, -59.95, 1.32],
        "bairros": ["Centro", "Jatapú", "Entre Rios", "Vicinal Norte", "Zona Rural"],
        "risk": "floresta",
    },
    {
        "codigo_ibge": "2927408",
        "nome": "Salvador",
        "uf": "BA",
        "populacao": 2418000,
        "area_km2": 693.8,
        "bbox": [-38.58, -13.03, -38.32, -12.82],
        "bairros": ["Centro Histórico", "Subúrbio Ferroviário", "Itapuã", "Brotas", "Cajazeiras", "Barra"],
        "risk": "encosta",
    },
    {
        "codigo_ibge": "4314902",
        "nome": "Porto Alegre",
        "uf": "RS",
        "populacao": 1333000,
        "area_km2": 495.4,
        "bbox": [-51.30, -30.18, -51.01, -29.93],
        "bairros": ["Centro Histórico", "Sarandi", "Menino Deus", "Restinga", "Moinhos de Vento", "Ilhas"],
        "risk": "inundacao",
    },
    {
        "codigo_ibge": "2507507",
        "nome": "João Pessoa",
        "uf": "PB",
        "populacao": 833000,
        "area_km2": 210.0,
        "bbox": [-34.98, -7.23, -34.79, -7.05],
        "bairros": ["Centro", "Manaíra", "Bessa", "Mangabeira", "Valentina", "Cabo Branco"],
        "risk": "costeiro",
    },
    {
        "codigo_ibge": "5201108",
        "nome": "Anápolis",
        "uf": "GO",
        "populacao": 420300,
        "area_km2": 935.7,
        "bbox": [-49.05, -16.45, -48.75, -16.15],
        "bairros": ["Centro", "Jundiaí", "Vila Jaiara", "Cidade Universitária", "Jardim Alvorada", "Vila Santa Maria"],
        "risk": "inundacao",
    },
    {
        "codigo_ibge": "4113700",
        "nome": "Londrina",
        "uf": "PR",
        "populacao": 580870,
        "area_km2": 1652.6,
        "bbox": [-51.35, -23.45, -50.95, -23.05],
        "bairros": ["Centro", "Gleba Fazenda Palhano", "Higienópolis", "Garcia", "Cafezal", "Nova Londrina"],
        "risk": "inundacao",
    },
]

RENDA_REFERENCIA_MENSAL = {
    # Estimativa demonstrativa de renda mensal per capita usada na versão interna.
    # Deve ser substituido por série oficial IBGE/PNAD ou cadastro local na carga real.
    "2611606": 1550.00,  # Recife - PE
    "1400233": 850.00,   # Caroebe - RR
    "2927408": 1350.00,  # Salvador - BA
    "4314902": 2450.00,  # Porto Alegre - RS
    "2507507": 1500.00,  # Joao Pessoa - PB
    "5201108": 1800.00,  # Anapolis - GO
    "4113700": 2200.00,  # Londrina - PR
}


def normalize_income_reference(db: Session):
    """Keeps demo census-sector income aligned with municipality-level references."""
    for codigo_ibge, renda_ref in RENDA_REFERENCIA_MENSAL.items():
        muni = db.query(Municipio).filter(Municipio.codigo_ibge == codigo_ibge).first()
        if not muni:
            continue

        setores = (
            db.query(SetorCensitario)
            .filter(SetorCensitario.municipio_id == muni.id)
            .order_by(SetorCensitario.id.asc())
            .all()
        )
        if not setores:
            continue

        factors = [0.75, 0.90, 1.05, 1.30]
        for idx, setor in enumerate(setores):
            setor.renda_media = round(renda_ref * factors[idx % len(factors)], 2)
    db.commit()


def _municipio_polygon(bbox):
    min_x, min_y, max_x, max_y = bbox
    return MultiPolygon([Polygon([
        [min_x, min_y],
        [max_x, min_y],
        [max_x, max_y],
        [min_x, max_y],
        [min_x, min_y],
    ])])


def _official_municipio_polygon(codigo_ibge, fallback_bbox):
    url = (
        "https://servicodados.ibge.gov.br/api/v3/malhas/municipios/"
        f"{codigo_ibge}?qualidade=minima&formato=application/vnd.geo+json"
    )
    try:
        response = requests.get(url, timeout=15)
        response.raise_for_status()
        geojson = response.json()
        features = geojson.get("features") or []
        if not features:
            return _municipio_polygon(fallback_bbox), "bbox_fallback"

        from shapely.geometry import shape

        geom = shape(features[0]["geometry"])
        if isinstance(geom, Polygon):
            geom = MultiPolygon([geom])
        elif not isinstance(geom, MultiPolygon):
            geom = MultiPolygon([part for part in geom.geoms if isinstance(part, Polygon)])

        if geom.is_empty:
            return _municipio_polygon(fallback_bbox), "bbox_fallback"
        return geom, "ibge"
    except Exception:
        return _municipio_polygon(fallback_bbox), "bbox_fallback"


def _grid_cells(poly, count):
    min_x, min_y, max_x, max_y = poly.bounds
    cols = 3
    rows = 2
    dx = (max_x - min_x) / cols
    dy = (max_y - min_y) / rows
    cells = []
    for row in range(rows):
        for col in range(cols):
            if len(cells) >= count:
                return cells
            x1 = min_x + col * dx
            y1 = min_y + row * dy
            cell = Polygon([[x1, y1], [x1 + dx, y1], [x1 + dx, y1 + dy], [x1, y1 + dy], [x1, y1]])
            clipped = poly.intersection(cell)
            if clipped.is_empty:
                continue
            if isinstance(clipped, Polygon):
                clipped = MultiPolygon([clipped])
            elif not isinstance(clipped, MultiPolygon):
                clipped = MultiPolygon([part for part in clipped.geoms if isinstance(part, Polygon)])
            if not clipped.is_empty:
                cells.append(clipped)
    while len(cells) < count:
        cells.append(poly)
    return cells


def _sector_cells(bairro_geom):
    min_x, min_y, max_x, max_y = bairro_geom.bounds
    mid_x = (min_x + max_x) / 2
    mid_y = (min_y + max_y) / 2
    raw_cells = [
        Polygon([[min_x, min_y], [mid_x, min_y], [mid_x, mid_y], [min_x, mid_y], [min_x, min_y]]),
        Polygon([[mid_x, min_y], [max_x, min_y], [max_x, mid_y], [mid_x, mid_y], [mid_x, min_y]]),
        Polygon([[min_x, mid_y], [mid_x, mid_y], [mid_x, max_y], [min_x, max_y], [min_x, mid_y]]),
        Polygon([[mid_x, mid_y], [max_x, mid_y], [max_x, max_y], [mid_x, max_y], [mid_x, mid_y]]),
    ]
    cells = []
    for cell in raw_cells:
        clipped = bairro_geom.intersection(cell)
        if clipped.is_empty:
            clipped = bairro_geom
        if isinstance(clipped, Polygon):
            clipped = MultiPolygon([clipped])
        elif not isinstance(clipped, MultiPolygon):
            clipped = MultiPolygon([part for part in clipped.geoms if isinstance(part, Polygon)])
        cells.append(clipped if not clipped.is_empty else bairro_geom)
    return cells


def _clear_demo_layers(db: Session, municipio_id: int):
    for model in (
        Bairro,
        SetorCensitario,
        HistoricoDesastreS2ID,
        AlertaCemaden,
        CoberturaVegetalMapBiomas,
        InfraestruturaUrbana,
    ):
        db.query(model).filter(model.municipio_id == municipio_id).delete(synchronize_session=False)
    db.commit()


def ensure_demo_municipalities(db: Session):
    for cfg in DEMO_MUNICIPIOS:
        existing = db.query(Municipio).filter(Municipio.codigo_ibge == cfg["codigo_ibge"]).first()
        muni_geom, _source = _official_municipio_polygon(cfg["codigo_ibge"], cfg["bbox"])
        if existing:
            muni = existing
            muni.nome = cfg["nome"]
            muni.uf = cfg["uf"]
            muni.populacao = cfg["populacao"]
            muni.area_km2 = cfg["area_km2"]
            muni.geom = f"SRID=4326;{muni_geom.wkt}"
            db.commit()
            db.refresh(muni)
            _clear_demo_layers(db, muni.id)
        else:
            muni = Municipio(
                codigo_ibge=cfg["codigo_ibge"],
                nome=cfg["nome"],
                uf=cfg["uf"],
                populacao=cfg["populacao"],
                area_km2=cfg["area_km2"],
                geom=f"SRID=4326;{muni_geom.wkt}",
            )
            db.add(muni)
            db.commit()
            db.refresh(muni)

        cells = _grid_cells(muni_geom, len(cfg["bairros"]))
        for idx, name in enumerate(cfg["bairros"]):
            bairro = Bairro(
                municipio_id=muni.id,
                nome=name,
                codigo_bairro=f"{cfg['codigo_ibge']}{idx + 1:02d}",
                geom=f"SRID=4326;{cells[idx].wkt}",
            )
            db.add(bairro)
        db.commit()

        bairros = db.query(Bairro).filter(Bairro.municipio_id == muni.id).all()
        for b_idx, bairro in enumerate(bairros):
            bairro_geom = cells[b_idx]
            income_base = 1800 + (b_idx % 3) * 1700
            pop_base = max(80, int(cfg["populacao"] / max(1, len(bairros) * 4)))
            for s_idx, sec_geom in enumerate(_sector_cells(bairro_geom)):
                db.add(SetorCensitario(
                    municipio_id=muni.id,
                    codigo_setor=f"{cfg['codigo_ibge']}{b_idx + 1:02d}{s_idx + 1:03d}",
                    populacao=int(pop_base * (0.8 + (s_idx * 0.15))),
                    renda_media=income_base * (0.85 + (s_idx * 0.1)),
                    geom=f"SRID=4326;{sec_geom.wkt}",
                ))

            min_x, min_y, max_x, max_y = bairro_geom.bounds
            mid_x = (min_x + max_x) / 2
            mid_y = (min_y + max_y) / 2
            left = MultiPolygon([Polygon([[min_x, min_y], [mid_x, min_y], [mid_x, max_y], [min_x, max_y], [min_x, min_y]])])
            right = MultiPolygon([Polygon([[mid_x, min_y], [max_x, min_y], [max_x, max_y], [mid_x, max_y], [mid_x, min_y]])])
            db.add(CoberturaVegetalMapBiomas(
                municipio_id=muni.id,
                ano=2025,
                classe_uso="Vegetação / Floresta" if b_idx % 2 == 0 else "Área Urbana",
                geom=f"SRID=4326;{left.wkt}",
            ))
            db.add(CoberturaVegetalMapBiomas(
                municipio_id=muni.id,
                ano=2025,
                classe_uso="Corpo d'água" if b_idx in (0, len(bairros) - 1) else "Área Urbana",
                geom=f"SRID=4326;{right.wkt}",
            ))

            center = Point(mid_x, mid_y)
            db.add(InfraestruturaUrbana(
                municipio_id=muni.id,
                tipo="hospital" if b_idx % 3 == 0 else "escola",
                nome=f"Equipamento público - {bairro.nome}",
                subgrupo="rede_publica",
                geom=f"SRID=4326;{center.wkt}",
            ))

        min_x, min_y, max_x, max_y = muni_geom.bounds
        db.add(InfraestruturaUrbana(
            municipio_id=muni.id,
            tipo="via",
            nome=f"Eixo estruturante - {cfg['nome']}",
            subgrupo="via_arterial",
            geom=f"SRID=4326;{LineString([[min_x, (min_y + max_y) / 2], [max_x, (min_y + max_y) / 2]]).wkt}",
        ))

        event_point = Point((min_x + max_x) / 2, (min_y + max_y) / 2)
        db.add(HistoricoDesastreS2ID(
            municipio_id=muni.id,
            tipo_desastre="Inundação" if cfg["risk"] in ("inundacao", "costeiro") else "Deslizamento",
            data_ocorrencia=datetime.date(2024, 5, 10),
            populacao_afetada=max(800, int(cfg["populacao"] * 0.03)),
            danos_materiais=max(1500000, int(cfg["populacao"] * 35)),
            geom=f"SRID=4326;{event_point.wkt}",
        ))

        alert_poly = _grid_cells(muni_geom, 1)[0]
        db.add(AlertaCemaden(
            municipio_id=muni.id,
            nivel_alerta="ALTO",
            descricao=f"Alerta demonstrativo Sinidu+Clima para risco urbano em {cfg['nome']}.",
            data_alerta=datetime.datetime.utcnow(),
            geom=f"SRID=4326;{alert_poly.wkt}",
        ))

        db.commit()

    normalize_income_reference(db)
