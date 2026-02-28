@echo off
REM Instagram Auto Post - Instalador Windows
REM Instala dependencias, cria pastas e configura o ambiente automaticamente.
setlocal enabledelayedexpansion

cd /d "%~dp0"

echo.
echo ==============================================
echo   Instagram Auto Post - Instalacao Windows
echo ==============================================
echo.

REM 1. Verificar Python
set PY=
where python >nul 2>&1
if %errorlevel% equ 0 set PY=python
if "%PY%"=="" (
    where py >nul 2>&1
    if %errorlevel% equ 0 set PY=py
)
if "%PY%"=="" (
    echo ERRO: Python nao encontrado.
    echo.
    echo Instala Python 3.10+ em: https://www.python.org/downloads/
    echo Marca "Add Python to PATH" durante a instalacao.
    pause
    exit /b 1
)
echo [1/6] Python encontrado.

REM 2. Criar ambiente virtual
if not exist ".venv\Scripts\activate.bat" (
    echo [2/6] A criar ambiente virtual .venv...
    %PY% -m venv .venv
) else (
    echo [2/6] Ambiente virtual ja existe.
)

call .venv\Scripts\activate.bat

REM 3. Instalar dependencias
echo [3/6] A instalar dependencias Python...
python -m pip install --upgrade pip -q
python -m pip install -r requirements.txt -q

REM 4. Criar pastas necessarias
echo [4/6] A criar pastas...
if not exist "assets\music\MUSIC" mkdir "assets\music\MUSIC"
if not exist "tools\ffmpeg" mkdir "tools\ffmpeg"
echo       assets\music\MUSIC - musica para Reels
echo       tools\ffmpeg - opcional: coloca ffmpeg.exe aqui

REM 5. Instalar Chromium para Playwright (Auto Click)
echo [5/6] A instalar Chromium para Playwright...
python -m playwright install chromium 2>nul
python -m playwright install-deps chromium 2>nul

REM 6. Configurar .env
echo [6/6] Configuracao .env...
if not exist ".env" (
    if exist ".env.example" (
        copy .env.example .env >nul
        echo       .env criado a partir de .env.example
        echo       Edita .env e preenche as credenciais (Google, Instagram, etc.).
    ) else (
        echo       Aviso: .env.example nao encontrado. Cria .env manualmente.
    )
) else (
    echo       .env ja existe.
)

echo.
echo ==============================================
echo   Instalacao concluida.
echo ==============================================
echo.
echo Para executar:
echo   run.bat
echo.
echo A app abre em: http://localhost:8502
echo.
pause
