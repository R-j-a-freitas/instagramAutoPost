# Contexto do projeto – Instagram Auto Post

*(Podes colar este bloco no chat do Cursor para dar contexto à conta / Google / Instagram.)*

---

## Contexto da conta / Google / Instagram

- **Email Google principal para esta automação:**  
  `clubtwocomma@gmail.com`

- **Instagram:**
  - Handle: **@keepcalmnbepositive**
  - Tipo de conteúdo: frases/afirmações em inglês (mindset, self‑love, healing, etc.).

- **Google Sheets (fonte de verdade dos posts):**
  - Título: **IG keepcalmnbepositive – Content**
  - ID: `1UBdukuHNvpfdcyBxKIQAt5pRIKFrGLYI6tZdYhfYCig`
  - Worksheet: **Folha1**
  - Estrutura oficial das colunas (ordem fixa):
    - **1. Date** – data do post (YYYY‑MM‑DD)
    - **2. Time** – hora do post (HH:MM)
    - **3. Image Text** – quote na imagem
    - **4. Caption** – texto “humano” de apoio (explicação/legenda)
    - **5. Gemini_Prompt** – prompt técnico para o Gemini criar a imagem
    - **6. Status** – ready / posted / etc.
    - **7. Published** – se já foi publicado no IG (yes / vazio)
    - **8. ImageURL** – URL da imagem final no Cloudinary
    - **9. Image Prompt** – estado/notas sobre a geração (ex.: "ok – Gemini+Cloudinary")

- **Estado atual do sheet (para a lógica):**
  - Linhas 2–6 → Date = 2026‑02‑09, já publicadas hoje → Published = "yes".
  - A partir da linha 7 em diante → 1 post por dia, com Status = "ready" e Published vazio.
  - Sequência de datas contínua: 2026‑02‑10 (linha 7) até pelo menos 2026‑02‑26 (linha 23).

---

## O que o dev/Cursor deve fazer

1. Usar **clubtwocomma@gmail.com** para configurar a service account / acesso ao Google Sheets (ou partilhar o Sheet com o email da service account criada no projeto).
2. Ler e escrever no Sheet `1UBdukuHNvpfdcyBxKIQAt5pRIKFrGLYI6tZdYhfYCig`, tab **Folha1**, respeitando as colunas e flags (Status, Published, ImageURL).
3. Implementar a lógica de:
   - escolher o próximo post com **Status = "ready"** e **Published** vazio, a partir de hoje pela Date/Time;
   - publicar no IG via **Instagram Graph API** usando a **Caption** (coluna 4) e a **ImageURL** (coluna 8);
   - se ImageURL vazio, gerar imagem com **Gemini_Prompt** (coluna 5) e upload para Cloudinary;
   - depois marcar **Published = "yes"** e **Status = "posted"** nessa linha.

---

*Última atualização: contexto da conta e sheet para @keepcalmnbepositive.*
