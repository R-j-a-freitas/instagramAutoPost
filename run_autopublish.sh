#!/bin/bash
cd "$(dirname "$0")"
if [ -f .venv/bin/activate ]; then source .venv/bin/activate; fi
if [ -f venv/bin/activate ]; then source venv/bin/activate; fi
python3 scripts/autopublish_cli.py
