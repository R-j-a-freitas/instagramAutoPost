@echo off
REM Instagram Auto Post - Executar app Streamlit localmente
cd /d "%~dp0"

REM Verificar se foi instalado
if not exist ".venv\Scripts\activate.bat" (
    if not exist "venv\Scripts\activate.bat" (
        echo Executa primeiro install.bat para instalar as dependencias.
        pause
        exit /b 1
    )
)

REM Ativar ambiente virtual
if exist ".venv\Scripts\activate.bat" (
    call .venv\Scripts\activate.bat
) else (
    call venv\Scripts\activate.bat
)

REM Iniciar Streamlit
echo A iniciar Streamlit...
python -m streamlit run app.py --server.port 8502 2>nul
if errorlevel 1 (
    py -m streamlit run app.py --server.port 8502
)
if errorlevel 1 (
    echo.
    echo Erro: Python/Streamlit nao encontrado. Instala com: pip install streamlit
    echo Depois executa: python -m streamlit run app.py --server.port 8502
)
pause
