#!/bin/bash
# Instagram Auto Post – Executar app Streamlit
cd "$(dirname "$0")"

# Ativar ambiente virtual se existir
if [ -f ".venv/bin/activate" ]; then
    source .venv/bin/activate
elif [ -f "venv/bin/activate" ]; then
    source venv/bin/activate
fi

echo "A iniciar Streamlit..."
# Porta 8502 para coincidir com OAUTH_REDIRECT_BASE no .env
python3 -m streamlit run app.py --server.port 8502
