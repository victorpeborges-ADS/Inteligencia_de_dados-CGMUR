#!/bin/bash
set -e

# Bibliotecas nativas do WeasyPrint (dev sem rebuild da imagem).
if ! ldconfig -p 2>/dev/null | grep -q 'libpango-1.0'; then
  apt-get update -qq
  apt-get install -y -qq --no-install-recommends \
    libglib2.0-0 libgirepository-1.0-1 \
    libpango-1.0-0 libpangocairo-1.0-0 libcairo2 libgdk-pixbuf-2.0-0 \
    fonts-liberation shared-mime-info 2>/dev/null || true
fi

# Dependências ausentes na imagem antiga — instala só o necessário (evita sentence-transformers a cada boot).
if ! python -c "import tenacity, pgvector, jwt, bcrypt, multipart" 2>/dev/null; then
  pip install -q \
  python-multipart \
  tenacity redis APScheduler openpyxl \
  weasyprint==62.3 pydyf==0.10.0 jinja2 pillow folium openmeteo-requests requests-cache matplotlib pytest \
  scikit-learn pyarrow rasterio \
  langchain-community langchain-text-splitters pypdf pyyaml pgvector \
  PyJWT bcrypt httpx
fi

# Modelos ML de alagamento — copia artifacts ou gera baseline se volume vazio
python -c "
from ml.bootstrap import ensure_flood_models
ensure_flood_models(None)
print('ML flood models ready')
" 2>/dev/null || echo "ML bootstrap skipped (will retry on first prediction)"

exec uvicorn main:app --host 0.0.0.0 --port 8000 --reload
