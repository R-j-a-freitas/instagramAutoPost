# YouTube → Áudio MP3

Documentação da página **YouTube Áudio** do Instagram Auto Post: descarregar o áudio de vídeos do YouTube em MP3 e opcionalmente guardá-lo na biblioteca de música dos Reels.

---

## O que faz

- **Entrada:** URL de um vídeo do YouTube (ex.: `https://www.youtube.com/watch?v=...` ou `https://youtu.be/...`).
- **Saída:** ficheiro MP3 (192 kbps) que podes transferir para o teu PC ou guardar na pasta de música dos Reels.

A conversão para MP3 é feita com **yt-dlp** (download) e **FFmpeg** (extração de áudio).

---

## FFmpeg no projeto

A aplicação **não exige** que tenhas FFmpeg instalado no sistema. Por defeito usa o FFmpeg fornecido pelo pacote Python **imageio-ffmpeg** (instalado com `pip install -r requirements.txt`).

### Ordem de procura do FFmpeg

1. **Pasta do projeto** — Se existir uma pasta com os executáveis do FFmpeg no projeto, essa é usada primeiro:
   - `tools/ffmpeg/` (com `ffmpeg.exe` e, recomendado, `ffprobe.exe`)
   - ou `ffmpeg/` na raiz do projeto
   - ou `tools/ffmpeg/bin` / `ffmpeg/bin`
2. **imageio-ffmpeg** — Se não encontrar nada nas pastas acima, usa o binário instalado pelo pacote **imageio-ffmpeg** (caminho completo do executável, pois o ficheiro tem nome com versão, ex.: `ffmpeg-win64-v4.2.2.exe`).

Se aparecer o erro *"ffprobe not found"*: o imageio-ffmpeg no Windows só inclui `ffmpeg`. Coloca uma build completa do FFmpeg (com `ffmpeg.exe` e `ffprobe.exe`) em `tools/ffmpeg/` — por exemplo descarregando de [gyan.dev](https://www.gyan.dev/ffmpeg/builds/) (ffmpeg-release-essentials) e extraindo a pasta `bin` para `tools/ffmpeg/`.

### Usar uma compilação própria (ex.: a partir do repositório git)

Se quiseres usar o FFmpeg compilado por ti a partir do código fonte oficial:

1. **Clonar o repositório**
   ```bash
   git clone https://git.ffmpeg.org/ffmpeg.git ffmpeg-src
   ```

2. **Compilar**  
   No Windows é necessário um ambiente de compilação (MSYS2 + MinGW ou Visual Studio). Guias oficiais:
   - [Documentação FFmpeg](https://ffmpeg.org/documentation.html)
   - [Guia de compilação](https://trac.ffmpeg.org/wiki/CompilationGuide)

3. **Copiar os executáveis para o projeto**  
   Coloca `ffmpeg.exe` (e preferencialmente `ffprobe.exe`) em:
   ```
   instagramAutoPost/tools/ffmpeg/
   ```
   Estrutura esperada:
   ```
   tools/ffmpeg/ffmpeg.exe
   tools/ffmpeg/ffprobe.exe
   ```

A aplicação deteta automaticamente estes ficheiros e usa este FFmpeg em vez do imageio-ffmpeg. Ver também `tools/ffmpeg/README.txt`.

---

## Guardar na pasta de música dos Reels

Após descarregar o áudio, podes:

1. **Transferir o MP3** — botão para guardar o ficheiro no teu computador.
2. **Guardar na pasta de música dos Reels** — opção para copiar o MP3 para `assets/music/MUSIC/`.  
   Para a faixa aparecer na página **Reels** (biblioteca de música), tens de adicionar uma entrada em `assets/music/metadata.json`, por exemplo:
   ```json
   {
     "tracks": [
       { "file": "nome_do_ficheiro.mp3", "name": "Nome da faixa", "duration_s": 120 }
     ]
   }
   ```

---

## Dependências

- **yt-dlp** — download de vídeo/áudio do YouTube (instalado via `requirements.txt`).
- **imageio-ffmpeg** — binários do FFmpeg usados por defeito (instalado via `requirements.txt`).

Não é necessário instalar FFmpeg manualmente no sistema nem configurar o PATH, a menos que queiras usar a tua própria compilação em `tools/ffmpeg/`.

---

## Ficheiros relacionados

| Ficheiro / pasta | Descrição |
|------------------|-----------|
| `pages/6_YouTube_Audio.py` | Página Streamlit YouTube Áudio |
| `tools/ffmpeg/` | Pasta opcional para colocar `ffmpeg.exe` e `ffprobe.exe` |
| `tools/ffmpeg/README.txt` | Instruções rápidas para FFmpeg no projeto |
| `assets/music/MUSIC/` | Pasta onde os Reels procuram ficheiros de música |
| `assets/music/metadata.json` | Lista de faixas disponíveis na página Reels |
