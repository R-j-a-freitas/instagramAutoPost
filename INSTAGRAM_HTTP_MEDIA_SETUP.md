# Configuração de Media: Cloudinary vs Local HTTP

Este documento descreve como configurar o backend de media para upload de imagens e vídeos gerados pela aplicação Instagram Auto Post.

## Conceitos

### Cloudinary (padrão)

- Imagens e vídeos são enviados para o serviço Cloudinary.
- O URL devolvido pelo Cloudinary é usado no Google Sheet e na Instagram Graph API.
- Requer conta Cloudinary e variáveis `CLOUDINARY_URL` ou `CLOUDINARY_CLOUD_NAME`, `CLOUDINARY_API_KEY`, `CLOUDINARY_API_SECRET`.

### Local HTTP

- Imagens e vídeos são guardados localmente em disco (`MEDIA_ROOT`).
- O URL passado ao Instagram e ao Sheet é `MEDIA_BASE_URL/<filename>` (ex.: `https://magnific1.ddns.net/ig_post_123_abc.png`).
- O nginx (ou outro servidor web) serve os ficheiros nesse domínio.
- Quando o Instagram faz fetch ao URL, obtém o ficheiro do nosso servidor.
- **Importante:** `MEDIA_BASE_URL` deve ser sempre um DNS público — o Instagram não consegue aceder a `localhost`.

---

## Variáveis de ambiente

| Variável        | Descrição                                                                 | Default              |
|-----------------|---------------------------------------------------------------------------|----------------------|
| `MEDIA_BACKEND` | `"cloudinary"` ou `"local_http"`                                         | `cloudinary`         |
| `MEDIA_ROOT`    | Directorio local onde as imagens/vídeos são gravados (modo local_http)    | `/srv/instagram_media` |
| `MEDIA_BASE_URL`| URL público servido por nginx (sem barra final)                          | `https://magnific1.ddns.net` |

---

## Configuração nginx (modo local_http)

O nginx deve servir os ficheiros de `MEDIA_ROOT` no domínio correspondente a `MEDIA_BASE_URL`.

Exemplo de configuração:

```nginx
server {
    listen 443 ssl;
    server_name magnific1.ddns.net;

    ssl_certificate /path/to/cert.pem;
    ssl_certificate_key /path/to/key.pem;

    location / {
        root /srv/instagram_media;
        try_files $uri $uri/ =404;
    }
}
```

- `root` deve coincidir com `MEDIA_ROOT`.
- A app e o nginx devem partilhar o mesmo `MEDIA_ROOT` (mesma máquina ou volume partilhado).

---

## Exemplos de .env

### Modo Cloudinary (actual)

```env
MEDIA_BACKEND=cloudinary
CLOUDINARY_URL=cloudinary://API_KEY:API_SECRET@CLOUD_NAME
```

### Modo local

```env
MEDIA_BACKEND=local_http
MEDIA_ROOT=/srv/instagram_media
MEDIA_BASE_URL=https://magnific1.ddns.net
```

### Modo local com porta

```env
MEDIA_BACKEND=local_http
MEDIA_ROOT=/srv/instagram_media
MEDIA_BASE_URL=https://magnific1.ddns.net:8000
```

### Desenvolvimento

- **Exemplo dev:** `MEDIA_BASE_URL=https://magnific1.ddns.net:8000` (DNS público, nunca localhost).
- O Instagram precisa de aceder ao URL; `localhost` não funciona.

### Windows

- `MEDIA_ROOT` deve ser um path explícito, ex.: `C:\caminho\instagram_media`.

---

## Topologia

- A app e o nginx devem partilhar o mesmo `MEDIA_ROOT` (mesma máquina ou volume partilhado).
- Os ficheiros são gravados pela app em `MEDIA_ROOT`; o nginx serve-os em `MEDIA_BASE_URL`.

---

## Migração Cloudinary → Local

Para migrar media existente do Cloudinary para o servidor local e actualizar o Sheet, usa o script:

```bash
python scripts/migrate_cloudinary_to_local.py
```

Com `--dry-run` para apenas listar o que seria migrado, sem gravar nem actualizar.

Pré-requisitos:

- `.env` com `MEDIA_BACKEND=local_http`, `MEDIA_ROOT`, `MEDIA_BASE_URL`
- Credenciais Google Sheets configuradas
