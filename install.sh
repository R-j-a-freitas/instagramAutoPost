#!/bin/bash
# Instagram Auto Post – Instalador Linux
# Instala dependências, cria pastas e configura o ambiente automaticamente.
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

echo ""
echo "=============================================="
echo "  Instagram Auto Post – Instalação Linux"
echo "=============================================="
echo ""

# 1. Verificar Python 3
if ! command -v python3 &> /dev/null; then
    echo "ERRO: Python 3 não encontrado."
    echo ""
    echo "Instala com:"
    echo "  Ubuntu/Debian: sudo apt install python3 python3-venv python3-pip"
    echo "  Fedora:        sudo dnf install python3 python3-pip"
    echo "  Arch:          sudo pacman -S python python-pip"
    exit 1
fi

PYTHON_VER=$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")' 2>/dev/null || echo "?")
echo "[1/6] Python $PYTHON_VER encontrado."

# 2. Criar ambiente virtual
if [ ! -d ".venv" ]; then
    echo "[2/6] A criar ambiente virtual (.venv)..."
    python3 -m venv .venv
else
    echo "[2/6] Ambiente virtual já existe."
fi

source .venv/bin/activate

# 3. Atualizar pip e instalar dependências
echo "[3/6] A instalar dependências Python..."
pip install --upgrade pip -q
pip install -r requirements.txt -q

# 4. Criar pastas necessárias
echo "[4/6] A criar pastas..."
mkdir -p assets/music/MUSIC
mkdir -p tools/ffmpeg
echo "      assets/music/MUSIC (música para Reels)"
echo "      tools/ffmpeg (opcional: coloca ffmpeg aqui)"

# 5. Instalar Chromium para Playwright (Auto Click)
echo "[5/6] A instalar Chromium para Playwright..."
python3 -m playwright install chromium 2>/dev/null || true
python3 -m playwright install-deps chromium 2>/dev/null || true

# 6. Configurar .env
echo "[6/6] Configuração .env..."
if [ ! -f ".env" ]; then
    if [ -f ".env.example" ]; then
        cp .env.example .env
        echo "      .env criado a partir de .env.example"
        echo "      Edita .env e preenche as credenciais (Google, Instagram, etc.)."
    else
        echo "      Aviso: .env.example não encontrado. Cria .env manualmente."
    fi
else
    echo "      .env já existe."
fi

# Tornar scripts executáveis
chmod +x run.sh install.sh 2>/dev/null || true

echo ""
echo "=============================================="
echo "  Instalação concluída."
echo "=============================================="
echo ""
echo "Para executar:"
echo "  ./run.sh"
echo ""
echo "A app abre em: http://localhost:8502"
echo ""
