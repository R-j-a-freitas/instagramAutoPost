# Instagram Auto Post

App em **Python + Streamlit** para automatizar posts no Instagram usando a **Instagram Graph API** oficial e um **Google Sheet** como fonte de verdade. As imagens são geradas por ti (por exemplo com Canva ou outra ferramenta) e colocas o link em cada linha no Sheet na coluna **ImageURL**; o script apenas publica.

## Estrutura do projeto

```
instagramAutoPost/
  instagram_poster/
    __init__.py
    config.py          # lê .env / secrets
    sheets_client.py   # interage com Google Sheets
    ig_client.py       # Instagram Graph API (criar + publicar media)
    scheduler.py       # lógica de escolha do próximo post e publicação
  app.py               # Streamlit (main)
  requirements.txt
  .env.example
  README.md
```

## Requisitos do Google Sheet

- **Aba** (ex.: `Folha1`) com as colunas:
  - **Date** (YYYY-MM-DD)
  - **Time** (HH:MM)
  - **Image Text** (texto que vai na imagem – informativo)
  - **Caption** (texto + hashtags para o post)
  - **Hashtags** (opcional, pode ser ignorado)
  - **Status** (`ready` / `posted`)
  - **Published** (`yes` ou vazio)
  - **ImageURL** – **URL público da imagem** (obrigatório para publicar; cada imagem é gerada por ti e o link colocado aqui)

Linha 1 = cabeçalho; dados a partir da linha 2.

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

### 3. Ficheiro `.env`

Copia `.env.example` para `.env` e preenche:

```env
IG_SHEET_ID=...
GOOGLE_SERVICE_ACCOUNT_JSON=/caminho/para/service_account.json

IG_BUSINESS_ID=...
IG_ACCESS_TOKEN=...

ENV=dev
```

## Como correr

1. Instala dependências:
   ```bash
   pip install -r requirements.txt
   ```
2. Garante que o `.env` está preenchido e que o Sheet está partilhado com a service account.
3. Executa a app Streamlit:
   - **Windows:** faz duplo-clique em `run.bat` ou, na pasta do projeto: `run.bat`
   - **Ou em qualquer SO:** `streamlit run app.py`
4. Abre o URL que o Streamlit mostrar no browser (normalmente `http://localhost:8501`).

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
