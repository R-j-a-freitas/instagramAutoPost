# Instagram Auto Post

App em **Python + Streamlit** para automatizar posts no Instagram usando a **Instagram Graph API** oficial e um **Google Sheet** como fonte de verdade.

**Imagens:** podes (1) preencher a coluna **ImageURL** no Sheet com um link manual, ou (2) deixar **ImageURL** vazio e preencher **Gemini_Prompt** — a app gera a imagem com **Gemini (Nano Banana)** e faz upload para **Cloudinary** antes de publicar.

## Estrutura do projeto

```
instagramAutoPost/
  instagram_poster/
    __init__.py
    config.py          # lê .env / secrets
    sheets_client.py   # interage com Google Sheets
    ig_client.py       # Instagram Graph API (criar + publicar media)
    scheduler.py       # lógica de escolha do próximo post e publicação
    image_generator.py # geração de imagens com Gemini (Nano Banana) + upload Cloudinary
  app.py               # Streamlit (main)
  requirements.txt
  .env.example
  README.md
```

## Requisitos do Google Sheet

- **Aba** (ex.: `Folha1`) com as colunas (ordem fixa):
  1. **Date** – data do post (YYYY-MM-DD)
  2. **Time** – hora do post (HH:MM)
  3. **Image Text** – quote na imagem
  4. **Caption** – texto “humano” de apoio (explicação/legenda)
  5. **Gemini_Prompt** – prompt técnico para o Gemini criar a imagem
  6. **Status** – ready / posted / etc.
  7. **Published** – se já foi publicado no IG (yes / vazio)
  8. **ImageURL** – URL da imagem final no Cloudinary
  9. **Image Prompt** – estado/notas sobre a geração (ex.: "ok – Gemini+Cloudinary")

Linha 1 = cabeçalho; dados a partir da linha 2. Se **ImageURL** estiver vazio, a app gera a imagem com **Gemini_Prompt** e faz upload para Cloudinary.

Para preencher **Gemini_Prompt** a partir do Image Text de cada linha, corre:
`py -m scripts.update_gemini_prompts` ou `run_update_prompts.bat` (requer .env com GOOGLE_SERVICE_ACCOUNT_JSON e IG_SHEET_ID).

## Configuração

### 1. Google Sheets (service account + partilha)

1. Abre [Google Cloud Console](https://console.cloud.google.com/) e cria um projeto (ou usa um existente).
2. Ativa a **Google Sheets API** e a **Google Drive API** para esse projeto.
3. Em **Credenciais** → **Criar credenciais** → **Conta de serviço**:
   - Cria uma conta de serviço e descarrega o ficheiro JSON (chave privada).
4. Guarda o JSON num sítio seguro (ex.: `./secrets/service_account.json`).
5. Partilha o teu Google Sheet com o **email da service account** (algo como `xxx@yyy.iam.gserviceaccount.com`) com permissão **Editor**, para a app poder ler e atualizar as células (Status, Published).

No `.env`:

- `GOOGLE_SERVICE_ACCOUNT_JSON=/caminho/para/service_account.json`
- `IG_SHEET_ID=` — ID do Sheet (está na URL: `https://docs.google.com/spreadsheets/d/ESTE_É_O_ID/edit`)

### 2. App Meta / Instagram (Instagram Graph API)

A publicação usa apenas a **Instagram Graph API** oficial (sem scraping nem automação do Instagram Web).

1. Cria uma **App** em [Meta for Developers](https://developers.facebook.com/).
2. Adiciona o produto **Instagram Graph API**.
3. Liga a tua conta Instagram **profissional** a uma **Página do Facebook** (obrigatório para a API de publicação).
4. Obtém:
   - **Instagram Business Account ID** (ID da conta IG profissional).
   - **Access Token** com permissões:
     - `instagram_basic` (ou `instagram_business_basic`)
     - `pages_show_list` / `pages_read_engagement`
     - `instagram_content_publish` (ou `instagram_business_content_publish`)

Documentação oficial:

- [Instagram Platform](https://developers.facebook.com/docs/instagram-api/)
- [Content Publishing](https://developers.facebook.com/docs/instagram-api/guides/content-publishing/)

No `.env`:

- `IG_BUSINESS_ID=` — ID da conta de negócios Instagram.
- `IG_ACCESS_TOKEN=` — token de acesso (idealmente long-lived).

### 4. Gemini (Nano Banana) + Cloudinary (geração automática de imagens)

Se quiseres que a app **gere as imagens** a partir da coluna **Gemini_Prompt** (em vez de preencheres ImageURL manualmente):

1. **Gemini API Key:** em [Google AI Studio](https://aistudio.google.com/apikey) cria uma API key e define no `.env`:
   - `GEMINI_API_KEY=...`
2. **Cloudinary:** cria uma conta em [cloudinary.com](https://cloudinary.com) (plano gratuito). No Dashboard, copia a **Cloudinary URL** (Environment variable) e define no `.env`:
   - `CLOUDINARY_URL=cloudinary://API_KEY:API_SECRET@CLOUD_NAME`

Documentação: [Nano Banana image generation](https://ai.google.dev/gemini-api/docs/image-generation).

Se **ImageURL** estiver preenchido no Sheet, a app usa esse URL e não chama a Gemini nem o Cloudinary.

### 5. Ficheiro `.env`

Copia `.env.example` para `.env` e preenche:

```env
IG_SHEET_ID=...
GOOGLE_SERVICE_ACCOUNT_JSON=/caminho/para/service_account.json

IG_BUSINESS_ID=...
IG_ACCESS_TOKEN=...

# Para gerar imagens a partir de Image Text:
GEMINI_API_KEY=...
CLOUDINARY_URL=cloudinary://...

ENV=dev
```

## Instalação e execução

### Instalação automática (recomendado)

- **Windows:** Duplo clique em `install.bat` → depois `run.bat`
- **Linux:** `chmod +x install.sh run.sh && ./install.sh` → depois `./run.sh`

O instalador cria o ambiente virtual, instala dependências, pastas e Chromium (Playwright). Ver [INSTALL_WINDOWS.md](INSTALL_WINDOWS.md), [INSTALL_LINUX.md](INSTALL_LINUX.md), [docs/MANUAL_UTILIZADOR.md](docs/MANUAL_UTILIZADOR.md) e [docs/AUTH.md](docs/AUTH.md) (login e utilizadores).

### Instalação manual

1. Instala dependências:
   ```bash
   pip install -r requirements.txt
   ```
2. Garante que o `.env` está preenchido e que o Sheet está partilhado com a service account.
3. Executa a app Streamlit:
   - **Windows:** `run.bat` ou `python -m streamlit run app.py --server.port 8502`
   - **Linux:** `./run.sh` ou `streamlit run app.py --server.port 8502`
4. Abre **http://localhost:8502** no browser.

## Fluxo de uso (exemplo)

1. **Atualizar o Sheet**  
   - Adiciona/edita linhas com Date, Time, Image Text, Caption, **ImageURL** (link público da imagem), Status = `ready`, Published em branco.

2. **Correr a app**  
   - `streamlit run app.py`

3. **Na interface**  
   - Vês a tabela dos próximos posts (Data, Hora, Image Text, preview da Caption, Status, Published).
   - **Post next** — publica o próximo post “ready” com Date ≤ hoje (e atualiza o Sheet: Published = yes, Status = posted).
   - **Post selected row** — publica a linha que escolheres no selectbox (útil para testar uma data/hora específica).

4. **Mensagens**  
   - Sucesso/erro aparecem na secção “Última ação” e, em caso de erro (ex.: ImageURL em branco, token inválido), na mensagem de erro.

## Scheduling (cron) no futuro

Esta versão **não** usa cron nem loops dentro do Streamlit; a publicação é sempre acionada por botão. Para publicar automaticamente a uma hora fixa, podes mais tarde integrar um cron no sistema (ou um worker externo) que, por exemplo, chame um script que use `run_publish_next()` do módulo `scheduler`.

## Licença

Uso livre no teu projeto.
