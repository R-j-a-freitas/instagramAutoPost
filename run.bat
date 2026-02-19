@echo off
REM Instagram Auto Post - Executar app Streamlit localmente
cd /d "%~dp0"

REM Ativar ambiente virtual se existir
if exist ".venv\Scripts\activate.bat" (
    call .venv\Scripts\activate.bat
) else if exist "venv\Scripts\activate.bat" (
    call venv\Scripts\activate.bat
)

REM Instalar dependências se necessário (descomenta a linha abaixo na primeira vez)
REM py -m pip install -r requirements.txt

echo A iniciar Streamlit...
REM Porta 8502 para coincidir com OAUTH_REDIRECT_BASE no .env (evita redirect_uri_mismatch)
py -m streamlit run app.py --server.port 8502

pause
