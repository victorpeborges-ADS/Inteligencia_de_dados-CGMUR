"""Códigos IBGE dos 61 municípios prioritários Sinidu+Clima."""

import os

TARGET_MUNICIPALITIES = [
    {"codigo_ibge": "1200401", "nome": "Rio Branco", "uf": "AC"},
    {"codigo_ibge": "2704302", "nome": "Maceió", "uf": "AL"},
    {"codigo_ibge": "1600303", "nome": "Macapá", "uf": "AP"},
    {"codigo_ibge": "1302603", "nome": "Manaus", "uf": "AM"},
    {"codigo_ibge": "2927408", "nome": "Salvador", "uf": "BA"},
    {"codigo_ibge": "2304400", "nome": "Fortaleza", "uf": "CE"},
    {"codigo_ibge": "5300108", "nome": "Brasília", "uf": "DF"},
    {"codigo_ibge": "3205309", "nome": "Vitória", "uf": "ES"},
    {"codigo_ibge": "5208707", "nome": "Goiânia", "uf": "GO"},
    {"codigo_ibge": "2111300", "nome": "São Luís", "uf": "MA"},
    {"codigo_ibge": "5103403", "nome": "Cuiabá", "uf": "MT"},
    {"codigo_ibge": "5002704", "nome": "Campo Grande", "uf": "MS"},
    {"codigo_ibge": "3106200", "nome": "Belo Horizonte", "uf": "MG"},
    {"codigo_ibge": "1501402", "nome": "Belém", "uf": "PA"},
    {"codigo_ibge": "2507507", "nome": "João Pessoa", "uf": "PB"},
    {"codigo_ibge": "4106902", "nome": "Curitiba", "uf": "PR"},
    {"codigo_ibge": "2611606", "nome": "Recife", "uf": "PE"},
    {"codigo_ibge": "2211001", "nome": "Teresina", "uf": "PI"},
    {"codigo_ibge": "3304557", "nome": "Rio de Janeiro", "uf": "RJ"},
    {"codigo_ibge": "2408102", "nome": "Natal", "uf": "RN"},
    {"codigo_ibge": "4314902", "nome": "Porto Alegre", "uf": "RS"},
    {"codigo_ibge": "1100205", "nome": "Porto Velho", "uf": "RO"},
    {"codigo_ibge": "1400100", "nome": "Boa Vista", "uf": "RR"},
    {"codigo_ibge": "4205407", "nome": "Florianópolis", "uf": "SC"},
    {"codigo_ibge": "2800308", "nome": "Aracaju", "uf": "SE"},
    {"codigo_ibge": "3550308", "nome": "São Paulo", "uf": "SP"},
    {"codigo_ibge": "1721000", "nome": "Palmas", "uf": "TO"},
    {"codigo_ibge": "3303906", "nome": "Petrópolis", "uf": "RJ"},
    {"codigo_ibge": "3303401", "nome": "Nova Friburgo", "uf": "RJ"},
    {"codigo_ibge": "3305802", "nome": "Teresópolis", "uf": "RJ"},
    {"codigo_ibge": "3550704", "nome": "São Sebastião", "uf": "SP"},
    {"codigo_ibge": "3300100", "nome": "Angra dos Reis", "uf": "RJ"},
    {"codigo_ibge": "4202404", "nome": "Blumenau", "uf": "SC"},
    {"codigo_ibge": "1504208", "nome": "Marabá", "uf": "PA"},
    {"codigo_ibge": "3143906", "nome": "Mariana", "uf": "MG"},
    {"codigo_ibge": "2914802", "nome": "Itabuna", "uf": "BA"},
    {"codigo_ibge": "2913606", "nome": "Ilhéus", "uf": "BA"},
    {"codigo_ibge": "4316907", "nome": "Santa Maria", "uf": "RS"},
    {"codigo_ibge": "3109006", "nome": "Brumadinho", "uf": "MG"},
    {"codigo_ibge": "2602902", "nome": "Cabo de Santo Agostinho", "uf": "PE"},
    {"codigo_ibge": "4318908", "nome": "São Luiz Gonzaga", "uf": "RS"},
    {"codigo_ibge": "3201506", "nome": "Colatina", "uf": "ES"},
    {"codigo_ibge": "1702109", "nome": "Araguaína", "uf": "TO"},
    {"codigo_ibge": "1400233", "nome": "Caroebe", "uf": "RR"},
    {"codigo_ibge": "2604106", "nome": "Caruaru", "uf": "PE"},
    {"codigo_ibge": "2407104", "nome": "Macaíba", "uf": "RN"},
    {"codigo_ibge": "2924009", "nome": "Paulo Afonso", "uf": "BA"},
    {"codigo_ibge": "2806701", "nome": "São Cristóvão", "uf": "SE"},
    {"codigo_ibge": "5201108", "nome": "Anápolis", "uf": "GO"},
    {"codigo_ibge": "5208905", "nome": "Goiás", "uf": "GO"},
    {"codigo_ibge": "5218805", "nome": "Rio Verde", "uf": "GO"},
    {"codigo_ibge": "4302105", "nome": "Bento Gonçalves", "uf": "RS"},
    {"codigo_ibge": "4304606", "nome": "Canoas", "uf": "RS"},
    {"codigo_ibge": "4104907", "nome": "Castro", "uf": "PR"},
    {"codigo_ibge": "4305108", "nome": "Caxias do Sul", "uf": "RS"},
    {"codigo_ibge": "3200607", "nome": "Aracruz", "uf": "ES"},
    {"codigo_ibge": "3509502", "nome": "Campinas", "uf": "SP"},
    {"codigo_ibge": "3138203", "nome": "Lavras", "uf": "MG"},
    {"codigo_ibge": "3548708", "nome": "São Bernardo do Campo", "uf": "SP"},
    {"codigo_ibge": "3549904", "nome": "São José dos Campos", "uf": "SP"},
    {"codigo_ibge": "3305505", "nome": "Saquarema", "uf": "RJ"},
]

TARGET_IBGE_CODES = [item["codigo_ibge"] for item in TARGET_MUNICIPALITIES]

IBGE_BASE_URL = "https://servicodados.ibge.gov.br/api/v3"
SICONFI_BASE_URL = "https://apidatalake.tesouro.gov.br/ords/siconfi/tt"
CAPAG_CKAN_URL = "https://www.tesourotransparente.gov.br/ckan/api/3/action/package_show?id=capag-municipios"

# Planilha exportada da Série Histórica SNIS ou tabelas do Diagnóstico AE (opcional).
SNIS_INDICADORES_URL = os.getenv("SNIS_INDICADORES_URL", "")

SICONFI_EXERCICIO = 2024
SICONFI_RREO_PERIODO = 6
SICONFI_RGF_PERIODO = 3
