"""Códigos IBGE do catálogo piloto Sinidu+Clima (8 municípios)."""

import os

# Ordem: boot/demo primeiro (Recife, Aracaju), capitais, depois PE LiDAR (PE3D).
TARGET_MUNICIPALITIES = [
    {"codigo_ibge": "2611606", "nome": "Recife", "uf": "PE"},
    {"codigo_ibge": "2800308", "nome": "Aracaju", "uf": "SE"},
    {"codigo_ibge": "2927408", "nome": "Salvador", "uf": "BA"},
    {"codigo_ibge": "3550308", "nome": "São Paulo", "uf": "SP"},
    {"codigo_ibge": "3304557", "nome": "Rio de Janeiro", "uf": "RJ"},
    {"codigo_ibge": "5300108", "nome": "Brasília", "uf": "DF"},
    {"codigo_ibge": "2603603", "nome": "Camutanga", "uf": "PE"},
    {"codigo_ibge": "2607604", "nome": "Ilha de Itamaracá", "uf": "PE"},
]

TARGET_IBGE_CODES = [item["codigo_ibge"] for item in TARGET_MUNICIPALITIES]

# Prioridade de boot / demo local (Recife + Aracaju). Override via BOOT_PRIORITY_IBGE_CODES.
BOOT_PRIORITY_IBGE_CODES = ["2611606", "2800308"]

IBGE_BASE_URL = "https://servicodados.ibge.gov.br/api/v3"
SICONFI_BASE_URL = "https://apidatalake.tesouro.gov.br/ords/siconfi/tt"
CAPAG_CKAN_URL = "https://www.tesourotransparente.gov.br/ckan/api/3/action/package_show?id=capag-municipios"

# Planilha exportada da Série Histórica SNIS ou tabelas do Diagnóstico AE (opcional).
SNIS_INDICADORES_URL = os.getenv("SNIS_INDICADORES_URL", "")

SICONFI_EXERCICIO = 2024
SICONFI_RREO_PERIODO = 6
SICONFI_RGF_PERIODO = 3
