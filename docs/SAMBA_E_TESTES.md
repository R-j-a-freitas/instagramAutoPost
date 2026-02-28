# Samba e partilha de media no servidor Linux

Este documento descreve como configurar uma pasta Samba partilhada no servidor Linux para o directorio de media do InstagramAutoPost, e como testar o funcionamento do sistema.

---

## 1. Por que usar Samba

Quando a aplicação e o nginx não correm na mesma máquina, ou quando queres aceder aos ficheiros de media a partir de outro sistema (ex.: Windows), uma partilha Samba permite:

- A app gravar em `MEDIA_ROOT` (que pode ser um mount da partilha)
- O nginx servir os mesmos ficheiros
- Acesso remoto para gestão ou backup

---

## 2. Instalação do Samba no servidor Linux

### 2.1. Ubuntu/Debian

```bash
sudo apt update
sudo apt install samba samba-common-bin
```

### 2.2. Verificar o serviço

```bash
sudo systemctl status smbd
sudo systemctl enable smbd   # arrancar ao boot
```

---

## 3. Criar a pasta e configurar a partilha

### 3.1. Criar o directorio de media

```bash
sudo mkdir -p /srv/instagram_media
sudo chown $USER:$USER /srv/instagram_media
chmod 755 /srv/instagram_media
```

### 3.2. Configurar a partilha Samba

Editar o ficheiro de configuração:

```bash
sudo nano /etc/samba/smb.conf
```

Adicionar no final (ou na secção `[homes]` se preferires outra estrutura):

```ini
[instagram_media]
   path = /srv/instagram_media
   browseable = yes
   read only = no
   guest ok = no
   valid users = @sambashare
   force create mode = 0664
   force directory mode = 0775
   create mask = 0664
   directory mask = 0775
```

**Nota:** Ajusta `valid users` conforme o utilizador que vai aceder (ex.: `ricardo` ou `@sambashare`).

### 3.3. Criar utilizador Samba

```bash
# Adicionar o utilizador ao grupo sambashare (se existir)
sudo usermod -aG sambashare $USER

# Definir password Samba para o utilizador (pode ser diferente da password Linux)
sudo smbpasswd -a $USER
```

### 3.4. Reiniciar o Samba

```bash
sudo systemctl restart smbd
sudo systemctl restart nmbd   # se instalado, para resolução de nomes
```

---

## 4. Montar a partilha noutro sistema

### 4.1. A partir de Linux (cliente)

```bash
# Instalar cliente
sudo apt install cifs-utils

# Criar ponto de montagem
sudo mkdir -p /mnt/instagram_media

# Montar (substituir USER, PASSWORD, SERVER pelo teu utilizador, password e IP/hostname)
sudo mount -t cifs //SERVER/instagram_media /mnt/instagram_media -o username=USER,password=PASSWORD,uid=$(id -u),gid=$(id -g)

# Montagem permanente: adicionar a /etc/fstab
# //SERVER/instagram_media /mnt/instagram_media cifs username=USER,password=PASSWORD,uid=1000,gid=1000,file_mode=0664,dir_mode=0775 0 0
```

### 4.2. A partir de Windows

1. Abrir o Explorador de Ficheiros
2. Na barra de endereço: `\\IP_DO_SERVIDOR\instagram_media`
3. Inserir credenciais quando pedido
4. Opcional: mapear como unidade de rede (clique direito → "Mapear unidade de rede")

---

## 5. Configuração nginx para servir a pasta de media

### 5.1. Bloco server para magnific1.ddns.net

O nginx deve ter `root` apontando para `/srv/instagram_media` e um `location /` que sirva os ficheiros. Exemplo:

```nginx
server {
    listen 443 ssl;
    server_name magnific1.ddns.net;

    ssl_certificate /etc/letsencrypt/live/magnific1.ddns.net/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/magnific1.ddns.net/privkey.pem;
    include /etc/letsencrypt/options-ssl-nginx.conf;
    ssl_dhparam /etc/letsencrypt/ssl-dhparams.pem;

    # Media local para InstagramAutoPost — os ficheiros ficam na raiz do dominio
    root /srv/instagram_media;
    autoindex off;

    # Outras aplicacoes (ex.: Guacamole) — location especificas primeiro
    location /guac/ {
        proxy_pass http://127.0.0.1:8080/guacamole/;
        proxy_cookie_path /guacamole/ /guac/;
        include proxy_params;
    }

    # Ficheiros de media na raiz: tenta servir o ficheiro, 404 se nao existir
    location / {
        try_files $uri =404;
    }
}
```

**Importante:** O `root` deve estar definido no server block. Se tiveres outros `location` blocks, o `location /` com `try_files` deve existir para servir ficheiros da raiz.

### 5.2. Aplicar e testar

```bash
# Verificar sintaxe
sudo nginx -t

# Recarregar nginx
sudo systemctl reload nginx

# Testar
curl -v https://magnific1.ddns.net/teste_nginx.txt
```

### 5.3. Se continuar 404 — verificar

1. **Qual ficheiro de config está activo:**
   ```bash
   ls -la /etc/nginx/sites-enabled/
   grep -r "magnific1" /etc/nginx/
   ```

2. **Se outro server block ou location tem prioridade:** O nginx usa a location mais específica. Um `location /guac/` não afecta `/teste_nginx.txt`. Mas um `location /` noutro sítio ou um `root` diferente pode.

3. **Confirmar que o ficheiro existe e tem permissões:**
   ```bash
   ls -la /srv/instagram_media/teste_nginx.txt
   # O nginx corre como www-data — o ficheiro deve ser legível
   sudo -u www-data cat /srv/instagram_media/teste_nginx.txt
   ```

4. **Ver qual server block responde ao pedido:**
   ```bash
   # Ver config activa para o server_name
   sudo nginx -T 2>/dev/null | grep -A 50 "server_name magnific1"
   ```

5. **Se o server block tiver root noutro sítio:** Por exemplo, se `root` for `/var/www/html`, os pedidos a `/teste_nginx.txt` procuram em `/var/www/html/teste_nginx.txt`. **Solução:** adicionar ou alterar para `root /srv/instagram_media;` no server block de magnific1.ddns.net e garantir que existe `location / { try_files $uri =404; }`.

---

## 6. Integração com InstagramAutoPost

### 6.1. Topologia recomendada

- **Servidor:** nginx + Samba + pasta `/srv/instagram_media`
- **App:** pode correr no mesmo servidor (grava em `/srv/instagram_media`) ou noutra máquina (monta a partilha e usa como `MEDIA_ROOT`)

### 6.2. Se a app correr noutra máquina

Na máquina da app, monta a partilha (ex.: `/mnt/instagram_media`) e define no `.env`:

```env
MEDIA_BACKEND=local_http
MEDIA_ROOT=/mnt/instagram_media
MEDIA_BASE_URL=https://magnific1.ddns.net
```

O nginx no servidor deve servir `/srv/instagram_media`. Se a partilha estiver montada na app e os ficheiros forem escritos na partilha, o servidor (que tem a pasta local) verá os ficheiros imediatamente.

---

## 7. Testes de funcionamento

### 7.1. Testar a partilha Samba

**No servidor:**

```bash
# Ver partilhas disponíveis
smbclient -L localhost -U $USER

# Aceder à partilha (modo interactivo)
smbclient //localhost/instagram_media -U $USER

# Dentro do smbclient:
# put ficheiro.txt    (enviar ficheiro)
# get ficheiro.txt    (obter ficheiro)
# ls                 (listar)
# exit
```

**De outro Linux:**

```bash
smbclient //IP_SERVIDOR/instagram_media -U USER
```

**De Windows:** Abrir `\\IP_SERVIDOR\instagram_media` e verificar se consegues criar/editar ficheiros.

---

### 7.2. Testar escrita na pasta de media

```bash
# No servidor (ou no mount)
echo "teste" > /srv/instagram_media/teste.txt
ls -la /srv/instagram_media/
```

---

### 7.3. Testar o nginx a servir ficheiros

```bash
# Criar ficheiro de teste
echo "conteudo publico" > /srv/instagram_media/teste_nginx.txt

# Testar (no próprio servidor ou de fora)
curl -v https://magnific1.ddns.net/teste_nginx.txt
```

Deve devolver `conteudo publico` com HTTP 200.

---

### 7.4. Testar a aplicação InstagramAutoPost

**Modo Cloudinary (baseline):**

1. Definir `MEDIA_BACKEND=cloudinary` no `.env`
2. Correr a app e publicar um post (ou gerar imagem de teste na Configuração)
3. Verificar que o ImageURL no Sheet é um URL Cloudinary

**Modo local_http:**

1. Definir no `.env`:
   ```env
   MEDIA_BACKEND=local_http
   MEDIA_ROOT=/srv/instagram_media
   MEDIA_BASE_URL=https://magnific1.ddns.net
   ```
2. Garantir que o nginx está a servir `/srv/instagram_media`
3. Gerar uma imagem de teste ou publicar um post
4. Verificar:
   - Ficheiro criado em `/srv/instagram_media/` (ex.: `ig_post_*.png`)
   - ImageURL no Sheet é `https://magnific1.ddns.net/ig_post_*.png`
   - `curl https://magnific1.ddns.net/ig_post_*.png` devolve a imagem

---

### 7.5. Teste end-to-end (publicação no Instagram)

1. Com `MEDIA_BACKEND=local_http` e nginx configurado
2. Publicar um post (imagem gerada ou ImageURL preenchido)
3. Verificar que o post aparece no Instagram
4. Se falhar com 400: confirmar que o URL é acessível publicamente (`curl` de fora da rede local)

---

### 7.6. Checklist rápido

| Teste | Comando / Acção | Resultado esperado |
|-------|-----------------|--------------------|
| Samba partilha | `smbclient -L localhost -U USER` | Lista `instagram_media` |
| Escrita pasta | `touch /srv/instagram_media/teste` | Sem erros |
| Nginx serve | `curl https://magnific1.ddns.net/teste_nginx.txt` | HTTP 200, conteúdo correto |
| App gera imagem | Publicar post ou teste na Config | Ficheiro em MEDIA_ROOT |
| URL público | `curl MEDIA_BASE_URL/ficheiro.png` | Imagem (bytes) |
| Instagram | Publicar post | Post visível no feed |

---

## 8. Resolução de problemas

**Samba: "Access denied"**
- Verificar `valid users` e `smbpasswd -a`
- Verificar permissões: `ls -la /srv/instagram_media`

**Nginx: 404**
- Verificar `root` no server block
- Verificar que o ficheiro existe e tem permissões de leitura

**Instagram: 400 Bad Request**
- O URL deve ser HTTPS e publicamente acessível
- Testar com `curl -I URL` de fora da rede

**App: "MEDIA_ROOT não gravável"**
- Verificar permissões do directorio
- Se for mount Samba, verificar que está montado (`mount | grep instagram`)
