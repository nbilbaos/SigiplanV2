# Despliegue de SIGIPLAN en producción (Vultr VPS · junto a Cívica)

Stack **autónomo y aislado** con Docker Compose. Convive con Cívica en el mismo VPS
**sin tocarla**: Cívica sigue en su puerto `8080`; Sigiplan estrena un **proxy nginx
dedicado** en el puerto `80` (que está libre), con **Cloudflare** delante para el
HTTPS. Diseñado para **migrar fácilmente** a un VPS propio después.

```
Internet ─► Cloudflare (TLS) ─► VPS :80 ─► edge_nginx (proxy compartido, enruta por dominio)
                                              └─ www.sigiplan.cl → sigiplan_app:5000
                                                                      │ red "web"
                                                                      └─► sigiplan_mongo (privado)
                                                   volúmenes: uploads, mongo_data

   (Cívica intacta:  VPS :8080 → civica-nginx → civica-app:8080)
```

- **app + Mongo** de Sigiplan: stack propio (`docker-compose.yml`), aislado. Mongo
  **no publica puertos**.
- **edge_nginx** (`deploy/docker-compose.proxy.yml`): único componente compartido,
  dueño del puerto 80. Enruta por dominio. No interfiere con Cívica (puerto 8080).
- **Cloudflare** termina el TLS; el origin va por HTTP. La app trae `ProxyFix` +
  cookies `Secure`, y el proxy reenvía `X-Forwarded-Proto=https` de Cloudflare.
- Migrar luego = mover este repo + los volúmenes `mongo_data` y `uploads`.

---

## 0. Prerrequisitos

1. **Cloudflare / DNS** — en la zona de tu dominio, crea registros **proxied
   (nube naranja)** apuntando a la IP del VPS:
   - `sigiplan.cl`      → `IP_DEL_VPS`
   - `www.sigiplan.cl`  → `IP_DEL_VPS`

2. **SSL/TLS en Cloudflare** — modo **Flexible** para arrancar hoy (Cloudflare habla
   HTTPS con el navegador y HTTP con el origin en :80). Activa **"Always Use HTTPS"**.
   > Endurecimiento recomendado luego: pasar a **Full (strict)** con un *Origin
   > Certificate* de Cloudflare y restringir el :80 del VPS a las IPs de Cloudflare
   > (firewall de Vultr) para que nadie llegue al origin saltándose Cloudflare.

3. **Firewall de Vultr** — abre **80/tcp** (además del 22 y el 8080 que ya usa Cívica).

4. **Swap** (si el VPS tiene 1 GB de RAM y no lo configuraste):
   ```bash
   sudo fallocate -l 1G /swapfile && sudo chmod 600 /swapfile
   sudo mkswap /swapfile && sudo swapon /swapfile
   echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab
   ```

---

## 1. Código y red compartida

```bash
sudo mkdir -p /opt/sigiplan && sudo chown $USER /opt/sigiplan
git clone <tu-repo> /opt/sigiplan
cd /opt/sigiplan

docker network create web   # red compartida proxy ↔ apps (si existe, ignora el aviso)
```

## 2. Secretos

```bash
cp .env.prod.example .env
openssl rand -hex 32   # → SECRET_KEY
openssl rand -hex 24   # → MONGO_PASSWORD
nano .env              # rellena SECRET_KEY, MONGO_PASSWORD y BOOTSTRAP_ADMIN_*
```
`.env` está en `.gitignore`: nunca se versiona.

## 3. Levantar Sigiplan (app + Mongo)

```bash
docker compose up -d --build
docker compose ps             # app y mongo "running"/"healthy"
docker compose logs -f app    # gunicorn arrancó
```

## 4. Levantar el proxy compartido (puerto 80)

```bash
docker compose -f deploy/docker-compose.proxy.yml up -d
docker compose -f deploy/docker-compose.proxy.yml logs -f proxy
```
`edge_nginx` toma el :80 y enruta `www.sigiplan.cl` → `sigiplan_app:5000`.
Cívica no se ve afectada (sigue en :8080).

## 5. Crear el SUPER_ADMIN inicial (sin datos de demo)

```bash
docker compose exec app python scripts/create_superadmin.py
```
> No ejecutes `seed.py` en producción: borra la base y carga datos ficticios.

## 6. Verificar

Abre **https://www.sigiplan.cl**, inicia sesión con `BOOTSTRAP_ADMIN_EMAIL` /
`BOOTSTRAP_ADMIN_PASSWORD` y **cambia la contraseña** desde *Mi Perfil*.

- ¿No carga? Revisa que el DNS de Cloudflare resuelva y que el :80 esté abierto en Vultr.
- ¿No puedes iniciar sesión (la cookie no “pega”)? Es el `X-Forwarded-Proto`: con
  Cloudflare en modo proxy debe llegar como `https`. El proxy ya lo reenvía; confirma
  que Cloudflare está en naranja (proxied), no en gris (DNS only).

---

## Operación

**Actualizar tras cambios de código**
```bash
cd /opt/sigiplan && git pull
docker compose up -d --build         # reconstruye la app; Mongo y datos intactos
```

**Recargar el proxy tras tocar `deploy/nginx/proxy.conf`**
```bash
docker compose -f deploy/docker-compose.proxy.yml exec proxy nginx -t
docker compose -f deploy/docker-compose.proxy.yml exec proxy nginx -s reload
```

**Backups de Mongo (cron diario)**
```bash
docker compose exec -T mongo sh -c \
  'mongodump --username "$MONGO_INITDB_ROOT_USERNAME" --password "$MONGO_INITDB_ROOT_PASSWORD" \
   --authenticationDatabase admin --archive --gzip' > sigiplan-$(date +%F).archive.gz

docker run --rm -v sigiplan_uploads:/data -v "$PWD":/out alpine \
  tar czf /out/sigiplan-uploads-$(date +%F).tar.gz -C /data .
```
Prueba la restauración al menos una vez (`mongorestore --archive --gzip --drop`).
Un backup no probado no es un backup.

---

## Sumar Cívica/Goventia a este proxy (más adelante)

Cuando Cívica tenga dominio y quieras unificar el front:
1. Mete `civica-app` (o su nginx) en la red `web` (añade `networks: [web]` + la red
   externa en su compose).
2. Descomenta el bloque de Cívica en `deploy/nginx/proxy.conf` con su subdominio.
3. `nginx -t && nginx -s reload`. Ya podrías retirar el mapeo `8080:80` de Cívica.

## Migrar Sigiplan a un VPS propio (cuando deje de ser MVP)

1. VPS viejo: backup de `mongo_data` (mongodump) y del volumen `uploads` (tar).
2. VPS nuevo: Docker, clona el repo, copia el `.env`, `docker network create web`.
3. `docker compose up -d --build`, restaura dump y uploads, levanta el proxy.
4. Repunta el DNS de `www.sigiplan.cl` en Cloudflare a la nueva IP.
