@echo off
REM Enviar projeto para GitHub
REM 1. Cria um repositório novo em https://github.com/new (vazio, sem README)
REM 2. Substitui YOUR_USERNAME e REPO_NAME abaixo pelo teu utilizador e nome do repo
REM 3. Executa este ficheiro

cd /d "%~dp0"

set REPO_URL=https://github.com/YOUR_USERNAME/REPO_NAME.git

git remote remove origin 2>nul
git remote add origin %REPO_URL%
git branch -M main
git push -u origin main

echo.
echo Se der erro de autenticacao, usa um Personal Access Token em https://github.com/settings/tokens
pause
