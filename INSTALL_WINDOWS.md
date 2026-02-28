# Instagram Auto Post – Instalação em Windows

## Requisitos

- Windows 10 ou superior
- Python 3.10 ou superior ([python.org](https://www.python.org/downloads/))
  - **Importante:** Marca "Add Python to PATH" durante a instalação

## Instalação rápida

1. Abre uma pasta no Explorador de Ficheiros e navega até `instagramAutoPost`
2. Duplo clique em **`install.bat`**
3. Espera a instalação terminar (pode demorar alguns minutos)
4. Duplo clique em **`run.bat`** para iniciar a app

## Passos manuais (alternativa)

```cmd
cd instagramAutoPost

REM 1. Criar ambiente virtual
python -m venv .venv
.venv\Scripts\activate.bat

REM 2. Instalar dependências
pip install -r requirements.txt

REM 3. Instalar Chromium (para Auto Click)
python -m playwright install chromium

REM 4. Configurar .env
copy .env.example .env
REM Edita .env com as tuas credenciais
```

## Executar

Duplo clique em **`run.bat`** ou, no terminal:

```cmd
run.bat
```

Ou manualmente:

```cmd
.venv\Scripts\activate.bat
python -m streamlit run app.py --server.port 8502
```

A app abre em **http://localhost:8502**

## Estrutura criada pelo instalador

| Pasta/Ficheiro | Descrição |
|----------------|-----------|
| `.venv/` | Ambiente virtual Python |
| `assets/music/MUSIC/` | Coloca ficheiros MP3 aqui para Reels |
| `tools/ffmpeg/` | Opcional: coloca ffmpeg.exe para YouTube Áudio |
| `.env` | Configuração (criado a partir de .env.example) |

## Autopublish em background (Task Scheduler)

Para publicar automaticamente sem manter a app aberta:

1. Abre **Agendador de Tarefas**
2. Cria uma nova tarefa
3. **Ação:** Iniciar programa → `run_autopublish.bat` (caminho completo)
4. **Gatilho:** Repetir a cada X minutos (ex.: 15)

## Resolução de problemas

### "Python não encontrado"
- Reinstala Python e marca **"Add Python to PATH"**
- Ou adiciona manualmente ao PATH: `C:\Users\...\AppData\Local\Programs\Python\Python3xx\`

### "Streamlit não encontrado"
- Executa primeiro `install.bat`
- Ou: `pip install streamlit`

### Erro ao instalar dependências
- Abre o terminal como Administrador
- Executa: `pip install -r requirements.txt`
