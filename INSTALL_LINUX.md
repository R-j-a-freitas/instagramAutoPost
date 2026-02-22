# Instagram Auto Post – Instalação em Linux

## Requisitos

- Python 3.10 ou superior
- pip

## Instalação rápida

```bash
cd instagramAutoPost
chmod +x install.sh run.sh
./install.sh
```

## Passos manuais (alternativa)

```bash
# 1. Criar ambiente virtual
python3 -m venv .venv
source .venv/bin/activate

# 2. Instalar dependências
pip install -r requirements.txt

# 3. Instalar Chromium (para Auto Click)
python3 -m playwright install chromium
python3 -m playwright install-deps chromium

# 4. Configurar .env
cp .env.example .env
# Edita .env com as tuas credenciais
```

## Executar

```bash
./run.sh
```

Ou:

```bash
source .venv/bin/activate
python3 -m streamlit run app.py --server.port 8502
```

A app abre em **http://localhost:8502**

## Dependências do sistema (Playwright Chromium)

Se o Chromium não arrancar, instala as dependências:

- **Ubuntu/Debian:**
  ```bash
  sudo apt install libnss3 libnspr4 libatk1.0-0 libatk-bridge2.0-0 libcups2 libdrm2 libxkbcommon0 libxcomposite1 libxdamage1 libxfixes3 libxrandr2 libgbm1 libasound2 libpango-1.0-0 libcairo2
  ```

- **Fedora:**
  ```bash
  sudo dnf install nss atk at-spi2-atk cups-libs libdrm libXcomposite libXdamage libXfixes libXrandr mesa-libgbm alsa-lib pango cairo
  ```

## Criar atalho no menu de aplicações (opcional)

Cria o ficheiro `~/.local/share/applications/instagram-auto-post.desktop`:

```ini
[Desktop Entry]
Name=Instagram Auto Post
Comment=Automação de publicações no Instagram
Exec=/caminho/completo/para/instagramAutoPost/run.sh
Icon=camera-photo
Terminal=true
Type=Application
Categories=Network;Graphics;
Path=/caminho/completo/para/instagramAutoPost
```

Substitui `/caminho/completo/para/instagramAutoPost` pelo teu caminho.
