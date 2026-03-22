#!/usr/bin/env bash
# stop_streamlit.sh - Mata o processo do Streamlit (porta 8502 por defeito)

set -e

PORT=${1:-8502}

pids=$(lsof -t -i:"${PORT}" || true)

if [ -z "$pids" ]; then
  echo "Nenhum processo a usar a porta ${PORT}."
  exit 0
fi

echo "A terminar processos na porta ${PORT}: $pids"
kill $pids 2>/dev/null || true
sleep 1

# Se ainda estiverem vivos, força com -9
pids_restantes=$(lsof -t -i:"${PORT}" || true)
if [ -n "$pids_restantes" ]; then
  echo "Forçar término (-9) de: $pids_restantes"
  kill -9 $pids_restantes 2>/dev/null || true
else
  echo "Processos terminados com sucesso."
fi
