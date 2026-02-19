@echo off
cd /d "%~dp0"
if exist .venv\Scripts\activate.bat call .venv\Scripts\activate.bat
if exist venv\Scripts\activate.bat call venv\Scripts\activate.bat
py scripts/autopublish_cli.py
