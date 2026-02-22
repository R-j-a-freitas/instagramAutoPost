#!/bin/bash
# Instagram Auto Post – Instalação em Linux
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

echo "=============================================="
echo "  Instagram Auto Post – Instalação Linux"
echo "=============================================="

# Verificar Python 3
if ! command -v python3 &> /dev/null; then
    echo "ERRO: Python 3 não encontrado. Instala com:"
    echo "  Ubuntu/Debian: sudo apt install python3 python3-venv python3-pip"
    echo "  Fedora:        sudo dnf install python3 python3-pip"
    echo "  Arch:          sudo pacman -S python python-pip"
    exit 1
fi

PYTHON_VER=$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
echo "Python $PYTHON_VER encontrado."

# Criar ambiente virtual
if [ ! -d ".venv" ]; then
    echo ""
    echo "A criar ambiente virtual (.venv)..."
    python3 -m venv .venv
fi

source .venv/bin/activate

# Atualizar pip
echo ""
echo "A atualizar pip..."
pip install --upgrade pip -q

# Instalar dependências
echo ""
echo "A instalar dependências..."
pip install -r requirements.txt

# Instalar browser Chromium para Playwright (Auto Click)
echo ""
echo "A instalar Chromium para Playwright..."
python3 -m playwright install chromium
python3 -m playwright install-deps chromium 2>/dev/null || true

# Ficheiro .env
if [ ! -f ".env" ]; then
    if [ -f ".env.example" ]; then
        echo ""
        echo "A criar .env a partir de .env.example..."
        cp .env.example .env
        echo "  Edita .env e preenche as credenciais (Google, Instagram, etc.)."
    else
        echo ""
        echo "Aviso: .env.example não encontrado. Cria .env manualmente."
    fi
else
    echo ""
    echo ".env já existe."
fi

# Tornar run.sh executável
chmod +x run.sh 2>/dev/null || true

echo ""
echo "=============================================="
echo "  Instalação concluída."
echo "=============================================="
echo ""
echo "Para executar:"
echo "  ./run.sh"
echo ""
echo "Ou manualmente:"
echo "  source .venv/bin/activate"
echo "  python3 -m streamlit run app.py --server.port 8502"
echo ""
echo "A app abre em: http://localhost:8502"
echo ""
