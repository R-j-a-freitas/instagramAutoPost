#!/bin/bash
# Enviar projeto para GitHub (Linux Version)

# 1. Cria um repositório novo em https://github.com/new (vazio, sem README) se ainda não existir.
# 2. Gera um Personal Access Token (PAT) em https://github.com/settings/tokens (classic)
#    com permissão 'repo'.

REPO_USER="R-j-a-freitas"
REPO_NAME="instagramAutoPost"

echo "=== GitHub Upload Script ==="

# Verifica se o git está inicializado
if [ ! -d ".git" ]; then
    echo "Inicializando Git..."
    git init
    git branch -M main
fi

# Configura o remote (garante que usa o utilizador correto)
git remote remove origin 2>/dev/null
git remote add origin "https://github.com/$REPO_USER/$REPO_NAME.git"

echo "A tentar fazer push para $REPO_USER/$REPO_NAME..."
echo "DICA: Se for pedido o password, usa o teu Personal Access Token do GitHub."

git push -u origin main

if [ $? -eq 0 ]; then
    echo "=== Sucesso! Projeto enviado. ==="
else
    echo "=== Erro no push. ==="
    echo "Se o erro for 403 (Permission Denied), o teu Git pode estar a tentar usar outra conta."
    echo ""
    echo "Solução recomendada: corre o comando abaixo substituindo O_TEU_TOKEN pelo teu token real:"
    echo "git remote set-url origin https://O_TEU_TOKEN@github.com/$REPO_USER/$REPO_NAME.git"
    echo "Depois tenta fazer push novamente: git push"
fi
