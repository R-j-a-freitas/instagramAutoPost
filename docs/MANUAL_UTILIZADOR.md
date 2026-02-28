# Instagram Auto Post — Manual do Utilizador

Manual completo de instalação, configuração e utilização da aplicação Instagram Auto Post.

---

## 1. Visão geral

A aplicação **Instagram Auto Post** automatiza a publicação de conteúdo no Instagram através da **Instagram Graph API** oficial, usando um **Google Sheet** como calendário editorial e fonte de verdade.

### Funcionalidades principais

| Módulo | Descrição |
|--------|-----------|
| **Posts** | Publicação automática de imagens com legenda |
| **Stories** | Stories automáticas associadas a cada post ou reutilização |
| **Reels** | Vídeos slideshow com música, publicação automática |
| **Comentários** | Autoresposta com emoji (uma resposta por comentário) |
| **Conteúdo IA** | Geração de quotes, captions e imagens com Gemini |
| **Autopublish** | Publicação 24/7 em background (Task Scheduler / cron) |
| **Auto Click** | Automação de cliques no browser (Playwright) |
| **YouTube Áudio** | Extração de áudio para Reels |

---

## 2. Executáveis disponíveis

### Windows

| Ficheiro | Descrição |
|----------|-----------|
| `install.bat` | Instalação automática (venv, dependências, Playwright, .env) |
| `run.bat` | Inicia a aplicação Streamlit em http://localhost:8502 |
| `run_autopublish.bat` | Executa o ciclo de autopublish (para Task Scheduler) |
| `run_update_prompts.bat` | Atualiza prompts Gemini no Google Sheet |
| `upload-github.bat` | Upload para repositório GitHub |

### Linux

| Ficheiro | Descrição |
|----------|-----------|
| `install.sh` | Instalação automática (venv, dependências, Playwright, .env) |
| `run.sh` | Inicia a aplicação Streamlit em http://localhost:8502 |
| `run_autopublish.sh` | Executa o ciclo de autopublish (para cron) |
| `run_update_prompts.sh` | Atualiza prompts Gemini no Google Sheet *(se existir)* |

**Nota:** No Linux, antes de executar os scripts, dá permissão de execução:

```bash
chmod +x install.sh run.sh run_autopublish.sh
```

---

## 3. Instalação

### 3.1 Windows

1. Instala **Python 3.10+** em [python.org](https://www.python.org/downloads/) e marca **"Add Python to PATH"**
2. Abre a pasta do projeto e faz duplo clique em **`install.bat`**
3. Aguarda a conclusão da instalação
4. Faz duplo clique em **`run.bat`** para iniciar a app

Ver detalhes em [INSTALL_WINDOWS.md](../INSTALL_WINDOWS.md).

### 3.2 Linux

```bash
cd instagramAutoPost
chmod +x install.sh run.sh run_autopublish.sh
./install.sh
./run.sh
```

Ver detalhes em [INSTALL_LINUX.md](../INSTALL_LINUX.md).

---

## 4. Configuração inicial

### 4.1 Ficheiro `.env`

O instalador cria `.env` a partir de `.env.example`. Edita `.env` com as tuas credenciais:

- **Google Sheets:** `IG_SHEET_ID`, OAuth ou Service Account
- **Instagram:** `INSTAGRAM_APP_ID`, `INSTAGRAM_APP_SECRET` (OAuth) ou `IG_BUSINESS_ID`, `IG_ACCESS_TOKEN`
- **Gemini:** `GEMINI_API_KEY` (geração de imagens)
- **Cloudinary:** `CLOUDINARY_URL` ou variáveis separadas (upload de imagens)
- **Media local:** `MEDIA_BACKEND`, `MEDIA_ROOT`, `MEDIA_BASE_URL` (se usares servidor HTTP)

### 4.2 Ligação na app

1. Abre **http://localhost:8502**
2. Vai a **Configuração**
3. Usa os botões **"Ligar com Google"** e **"Ligar com Instagram"** para OAuth
4. Clica em **"Verificar todas as ligações"** para validar

---

## 5. Google Sheet (calendário)

O Sheet deve ter uma aba com as colunas (ordem fixa):

| Coluna | Descrição |
|--------|-----------|
| Date | Data do post (YYYY-MM-DD) |
| Time | Hora (HH:MM) |
| Image Text | Quote na imagem |
| Caption | Legenda do post |
| Gemini_Prompt | Prompt para gerar imagem (se ImageURL vazio) |
| Status | ready / posted / etc. |
| Published | yes / vazio |
| ImageURL | URL da imagem (Cloudinary ou servidor local) |
| Image Prompt | Notas sobre a geração |

Linha 1 = cabeçalho; dados a partir da linha 2.

---

## 6. Módulos da aplicação

### 6.1 Configuração

- Ligar Google e Instagram via OAuth
- Definir intervalo do Autopublish
- Configurar backend de media (Cloudinary / local HTTP)
- Verificar todas as ligações

### 6.2 Gestão de Posts

- Ver próximos posts do Sheet
- Publicar manualmente (próximo ou linha selecionada)
- Atualizar Status e Published no Sheet

### 6.3 Criar Conteúdo

- Gerar quotes e captions com IA
- Gerar imagens com Gemini e upload para Cloudinary

### 6.4 Autopublish

- Histórico de publicações automáticas
- Configurar intervalo (minutos)
- Executar ciclo manualmente

### 6.5 Stories

- Publicar Stories associadas a posts
- Reutilizar Stories existentes

### 6.6 Reels

- Criar Reels slideshow com música
- Colocar MP3 em `assets/music/MUSIC/`

### 6.7 YouTube Áudio

- Extrair áudio de vídeos YouTube para Reels
- Requer ffmpeg em `tools/ffmpeg/`

### 6.8 Comentários

- Configurar autoresposta a comentários
- Uma resposta por comentário (emoji)

### 6.9 Auto Click

- Automação de cliques no browser (Playwright Chromium)

---

## 7. Autopublish em background

Para publicar automaticamente 24/7 sem manter o browser aberto:

### Windows (Task Scheduler)

1. Abre **Agendador de Tarefas**
2. Cria uma nova tarefa
3. **Ação:** Iniciar programa → `run_autopublish.bat` (caminho completo)
4. **Gatilho:** Repetir a cada X minutos (ex.: 15)

### Linux (cron)

```bash
# Editar crontab
crontab -e

# Executar a cada 15 minutos
*/15 * * * * /caminho/completo/para/instagramAutoPost/run_autopublish.sh
```

---

## 8. Publicação no servidor

Para publicar a aplicação e a apresentação num servidor web:

### 8.1 Estrutura de ficheiros

- **App Streamlit:** corre em `http://servidor:8502` (ou atrás de proxy reverso)
- **Apresentação HTML:** `docs/apresentacao.html` — pode ser servida pelo nginx ou outro servidor web

### 8.2 Servir a apresentação com nginx

1. Copia `docs/apresentacao.html` para o diretório web do servidor (ex.: `/var/www/html/` ou `/srv/instagram_media/`)
2. Configura o nginx para servir o ficheiro:

```nginx
location /apresentacao {
    alias /caminho/para/apresentacao.html;
}
```

Ou coloca `apresentacao.html` como `index.html` numa pasta dedicada.

### 8.3 App Streamlit no servidor

1. Instala a app no servidor (Linux): `./install.sh`
2. Configura o `.env` com credenciais de produção
3. Executa com `./run.sh` ou como serviço systemd
4. Opcional: usa nginx como proxy reverso para `http://127.0.0.1:8502`

### 8.4 Media e Samba

Para partilha de ficheiros de media entre máquinas, consulta [SAMBA_E_TESTES.md](SAMBA_E_TESTES.md).

---

## 9. Resolução de problemas

### Python não encontrado (Windows)

- Reinstala Python e marca **"Add Python to PATH"**

### Streamlit não encontrado

- Executa `install.bat` ou `install.sh` primeiro
- Ou: `pip install streamlit`

### Erro ao ligar Google/Instagram

- Verifica as URIs de redirecionamento (ex.: `http://localhost:8502/` se a app corre na porta 8502)
- Define `OAUTH_REDIRECT_BASE=http://localhost:8502` no `.env`

### Chromium não arranca (Linux)

- Instala dependências: `python3 -m playwright install-deps chromium`
- Ver dependências em [INSTALL_LINUX.md](../INSTALL_LINUX.md)

### Imagens não aparecem

- Se usas `local_http`: verifica `MEDIA_ROOT` e `MEDIA_BASE_URL`
- Confirma que o nginx serve a pasta de media (ver [SAMBA_E_TESTES.md](SAMBA_E_TESTES.md))

---

## 10. Documentação adicional

- [INSTALL_WINDOWS.md](../INSTALL_WINDOWS.md) — Instalação Windows
- [INSTALL_LINUX.md](../INSTALL_LINUX.md) — Instalação Linux
- [SAMBA_E_TESTES.md](SAMBA_E_TESTES.md) — Samba e publicação no servidor
- [README.md](../README.md) — Visão geral do projeto
