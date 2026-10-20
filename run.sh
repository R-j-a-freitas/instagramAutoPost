#!/bin/bash
# Instagram Auto Post – Executar app Streamlit
cd "$(dirname "$0")"

# Verificar se foi instalado
if [ ! -f ".venv/bin/activate" ] && [ ! -f "venv/bin/activate" ]; then
    echo "Executa primeiro ./install.sh para instalar as dependências."
    exit 1
fi

# Ativar ambiente virtual
if [ -f ".venv/bin/activate" ]; then
    source .venv/bin/activate
else
    source venv/bin/activate
fi

echo "A iniciar Streamlit..."
# Porta 8502 para coincidir com OAUTH_REDIRECT_BASE no .env
# start_app.py liga o autopublish logo no arranque (sem esperar que alguém abra a página) e corre o Streamlit
python3 start_app.py --server.port 8502
