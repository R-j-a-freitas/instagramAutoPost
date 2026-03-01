# Autenticação — Login e gestão de utilizadores

Documentação do sistema de login da aplicação Instagram Auto Post.

---

## 1. Visão geral

A aplicação exige **login com email e password** antes de aceder a qualquer página. O utilizador padrão é `clubtwocomma@gmail.com`; a password é definida na **primeira utilização**.

### Fluxo

1. **Primeira utilização:** a app mostra o formulário "Primeira utilização para [email]. Define a password de acesso."
2. O utilizador introduz a nova password duas vezes (confirmação).
3. A password é guardada (hash com salt) no ficheiro `.auth.json`.
4. **Utilizações seguintes:** login com email e password.
5. **Terminar sessão:** botão na barra lateral.

---

## 2. Configuração no `.env`

### Variáveis disponíveis

| Variável | Descrição | Valor por defeito |
|----------|-----------|-------------------|
| `AUTH_ENABLED` | Ativa ou desativa o login | `true` |
| `AUTH_ALLOWED_USERS` | Emails autorizados (separados por vírgula) | `clubtwocomma@gmail.com` |

### Exemplos

**Apenas o utilizador padrão:**
```env
# Não definir AUTH_ALLOWED_USERS — usa clubtwocomma@gmail.com
```

**Múltiplos utilizadores:**
```env
AUTH_ALLOWED_USERS=clubtwocomma@gmail.com,maria@empresa.pt,joao@empresa.pt
```

**Desativar login (desenvolvimento):**
```env
AUTH_ENABLED=false
```

---

## 3. Adicionar novos utilizadores

### Passo a passo

1. Edita o ficheiro `.env` na raiz do projeto.
2. Adiciona ou altera a linha `AUTH_ALLOWED_USERS`:

   ```env
   AUTH_ALLOWED_USERS=clubtwocomma@gmail.com,novo@email.com,outro@email.com
   ```

3. Reinicia a aplicação (`run.bat` ou `run.sh`).
4. O novo utilizador acede à app, introduz o email e define a password na primeira vez.

### Regras

- Emails separados por **vírgula** (sem espaços ou com espaços — são ignorados).
- Cada utilizador define a **sua própria password** na primeira entrada.
- O ficheiro `.auth.json` guarda as passwords (em hash) automaticamente.
- Não é necessário criar contas manualmente — basta adicionar o email à lista.

---

## 4. Ficheiro `.auth.json`

As credenciais são guardadas em `.auth.json` na raiz do projeto:

- **Não versionado** (está no `.gitignore`).
- Formato interno: `{"users": {"email@x.com": {"salt": "...", "hash": "..."}}}`
- **Não editar manualmente** — as passwords estão em hash e o salt é gerado automaticamente.

### Repor a password de um utilizador

Para forçar um utilizador a redefinir a password:

1. Abre `.auth.json`.
2. Remove a entrada do email em `users` (ex.: apaga `"email@x.com": {...}`).
3. Guarda o ficheiro.
4. Na próxima entrada, o utilizador verá o formulário "Primeira utilização" e define nova password.

---

## 5. Segurança

- **Hash:** SHA-256 com salt aleatório (16 bytes em hex).
- **Salt:** único por utilizador, gerado com `secrets.token_hex(16)`.
- **Ficheiro:** `.auth.json` não deve ser partilhado nem enviado para repositórios.
- **HTTPS:** em produção, serve a app via HTTPS para proteger a password em trânsito.

---

## 6. Resolução de problemas

### "Este email não está autorizado"

- Verifica se o email está em `AUTH_ALLOWED_USERS` no `.env`.
- Confirma que não há espaços a mais ou erros de escrita no email.
- Reinicia a app após alterar o `.env`.

### "Password incorreta" (mas a password está certa)

- Pode ter havido alteração no `.auth.json` ou no algoritmo.
- Repõe a password removendo o utilizador de `.auth.json` (ver secção 4).

### Login não aparece / acesso direto

- Confirma que `AUTH_ENABLED` não está definido como `false` no `.env`.
- Se `AUTH_ENABLED=false`, o login está desativado.

---

## 7. Documentação relacionada

- [MANUAL_UTILIZADOR.md](MANUAL_UTILIZADOR.md) — secção 4 (Autenticação)
- [.env.example](../.env.example) — variáveis de autenticação
