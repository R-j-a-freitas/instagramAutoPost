@echo off
REM Preencher Gemini_Prompt no Sheet a partir do Image Text de cada linha
cd /d "%~dp0"

if exist ".venv\Scripts\activate.bat" (call .venv\Scripts\activate.bat)
if exist "venv\Scripts\activate.bat" (call venv\Scripts\activate.bat)

echo A preencher Gemini_Prompt...
py -m scripts.update_gemini_prompts

pause
