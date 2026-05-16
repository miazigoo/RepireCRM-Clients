# Repair CRM Client

Отдельная клиентская часть Repair CRM. Приложение использует только публичный API
кабинета клиента (`/api/portal`) и не содержит экранов сотрудников, админки,
склада, отчетов или внутренней авторизации CRM.

## Возможности

- регистрация и вход клиента по телефону или email, политика настраивается;
- refresh-сессии для веба и будущего мобильного приложения;
- быстрый просмотр статуса по номеру заказа и телефону;
- список клиентских заявок, этапы ремонта и публичные комментарии;
- создание онлайн-заявки на ремонт;
- согласование или отклонение работ с комментарием клиента;
- sync API для обмена заказами и действиями с рабочей CRM;
- заготовки mobile push/device API для будущего приложения;
- подготовка лендинга под SEO и контекстную рекламу: meta/OG/canonical,
  JSON-LD, sitemap, robots.txt, UTM/gclid/yclid capture, события CTA;
- защита от XSS/JS-инъекций через CSP/security headers и очистку текстовых полей.

## Структура

- `frontend/` - Angular клиентский кабинет.
- `backend/` - FastAPI API, миграции, sync-worker и тесты.
- `docker/` - nginx/backend Dockerfile и runtime-конфиги.

## Локальная разработка

### Быстрый старт через Docker

```bash
cp .env.example .env
make up
```

| Сервис | Адрес |
|--------|-------|
| Frontend (nginx) | <http://127.0.0.1:4300> |
| Backend API | <http://127.0.0.1:8040> |
| API docs (Swagger) | <http://127.0.0.1:8040/api/docs> |
| Health check | <http://127.0.0.1:8040/api/health> |
| PostgreSQL | `127.0.0.1:55440` |
| Redis | `127.0.0.1:56379` |

Основные команды:

```bash
make up            # запустить контейнеры
make down          # остановить
make build         # пересобрать образы
make logs          # логи всех сервисов
make migrate       # применить миграции
make test          # запустить тесты
```

### Frontend без Docker

```bash
cd frontend
npm install
npm run start:dev
```

Dev-сервер стартует на <http://127.0.0.1:4300>, запросы `/api` проксируются на
`http://127.0.0.1:8040`. Для другого backend:

```bash
API_TARGET=http://127.0.0.1:8041 npm run start:dev
```

### Backend без Docker

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt
alembic -c alembic.ini upgrade head
uvicorn app.main:app --reload --host 0.0.0.0 --port 8040
```

### Тесты

```bash
# Backend
backend/.venv/bin/pytest backend/tests -v

# Frontend
cd frontend && npm run build && npm run test:ci
```

## Деплой в production

### Требования к серверу

- Linux (Ubuntu 22.04+), минимум 1 CPU / 1 GB RAM / 10 GB SSD.
- Docker + Docker Compose v2.
- Nginx на хосте (не в контейнере) для проксирования.
- Домен с A-записью, указывающей на IP сервера.
- Порты 80 и 443 открыты в firewall.

### 1. Клонирование

```bash
mkdir -p /opt/repaircrm/client
cd /opt/repaircrm/client
git clone https://github.com/YOUR_ORG/RepireCRM-Clients.git .
```

### 2. Переменные окружения

```bash
cp .env.example .env.production
nano .env.production
```

Обязательные переменные:

```env
CLIENT_PORTAL_SECRET_KEY=<минимум 50 случайных символов>
CLIENT_PORTAL_DATABASE_URL=postgresql+psycopg://repaircrm_client:PASSWORD@postgres:5432/repaircrm_client
CLIENT_PORTAL_SYNC_API_KEY=<тот же sync token, что в CRM-интеграции>
CLIENT_PORTAL_TENANT_KEY=repair-demo
CLIENT_PORTAL_CORS_ORIGINS=https://repire-status.ru,https://www.repire-status.ru
CLIENT_PORTAL_PUBLIC_SITE_URL=https://repire-status.ru
CLIENT_PORTAL_DELIVERY_DEBUG=false

# Обратный trigger CRM sync из worker клиента
CLIENT_PORTAL_CRM_BASE_URL=https://b00bs.ru
CLIENT_PORTAL_CRM_API_KEY=<sync token CRM-интеграции>
CLIENT_PORTAL_CRM_TENANT_KEY=repair-demo
```

Сгенерировать `SECRET_KEY`:

```bash
python3 -c "import secrets; print(secrets.token_urlsafe(64))"
```

### 3. Запуск контейнеров

```bash
docker compose --env-file .env.production -p repaircrm-client up -d --build
```

Compose поднимает: `backend` (FastAPI/Uvicorn), `frontend` (nginx + Angular SPA),
`db` (PostgreSQL), `redis`, `worker` (sync-worker). Миграции применяются
автоматически.

Проверка:

```bash
docker compose -p repaircrm-client ps
curl http://localhost:8081/
curl http://localhost:8040/api/health
```

Повторяемый production-деплой с backup-before-deploy и smoke-проверками:

```bash
DEPLOY_HOST=130.49.151.251 \
DEPLOY_DOMAIN=repire-status.ru \
scripts/deploy-production.sh
```

Скрипт сохраняет серверный `.env.production`, делает dump PostgreSQL в
`/opt/repaircrm/client/backups/pre-deploy`, пересобирает контейнеры и проверяет
`/api/health`, `/robots.txt`, `/sitemap.xml`, `/login`.

### 4. Nginx — хостовый reverse proxy

Создайте или добавьте в существующий конфиг:

```nginx
upstream repaircrm_client_frontend {
    server 127.0.0.1:8081;
    keepalive 32;
}

server {
    listen 80;
    server_name repire-status.ru www.repire-status.ru;
    client_max_body_size 25m;

    location / {
        proxy_pass         http://repaircrm_client_frontend;
        proxy_http_version 1.1;
        proxy_set_header   Upgrade $http_upgrade;
        proxy_set_header   Connection "upgrade";
        proxy_set_header   Host $host;
        proxy_set_header   X-Real-IP $remote_addr;
        proxy_set_header   X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header   X-Forwarded-Proto $scheme;
    }
}
```

```bash
nginx -t && systemctl reload nginx
```

### 5. SSL — Let's Encrypt / Certbot

Установка (если ещё нет):

```bash
apt install -y certbot python3-certbot-nginx
```

Выпуск сертификата — Certbot сам правит nginx и настраивает HTTP → HTTPS редирект:

```bash
certbot --nginx \
  --non-interactive --agree-tos \
  --email admin@b00bs.ru \
  -d repire-status.ru -d www.repire-status.ru \
  --redirect
```

> **Важно:** до запуска Certbot домен должен быть прописан в DNS и резолвиться на
> IP сервера. Проверить: `dig +short repire-status.ru`

Проверка автопродления:

```bash
certbot renew --dry-run
systemctl status certbot.timer   # должен быть active
```

После получения TLS обновите `.env.production`:

```env
CLIENT_PORTAL_CORS_ORIGINS=https://repire-status.ru,https://www.repire-status.ru
CLIENT_PORTAL_PUBLIC_SITE_URL=https://repire-status.ru
```

И перезапустите backend:

```bash
docker compose -p repaircrm-client up -d --no-deps backend
```

### 6. SEO и контекстная реклама

Для рекламного домена укажите публичный URL и, при необходимости, счетчики:

```env
CLIENT_PORTAL_PUBLIC_SITE_URL=https://repire-status.ru
CLIENT_PORTAL_GOOGLE_TAG_ID=G-XXXXXXXXXX
CLIENT_PORTAL_YANDEX_METRIKA_ID=12345678
```

Frontend-контейнер генерирует `assets/runtime-config.js` на старте, поэтому для
смены счетчиков достаточно обновить env и перезапустить контейнер `frontend`.

Проверки после деплоя:

```bash
curl https://repire-status.ru/robots.txt
curl https://repire-status.ru/sitemap.xml
```

Лендинг сам выставляет `title`, `description`, canonical, Open Graph и JSON-LD
по данным бренда, акциям и точкам обслуживания из CRM. Страница `/login`
помечена как `noindex`, потому что это приватная часть кабинета.

### 6. Автозапуск при перезагрузке

```bash
cat > /etc/systemd/system/repaircrm-client.service << 'EOF'
[Unit]
Description=Repair CRM Client Portal Docker stack
After=docker.service
Requires=docker.service

[Service]
Type=oneshot
RemainAfterExit=yes
WorkingDirectory=/opt/repaircrm/client
ExecStart=docker compose --env-file .env.production -p repaircrm-client up -d
ExecStop=docker compose -p repaircrm-client down
TimeoutStartSec=300

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable repaircrm-client
```

### 7. Обновление

Из локального checkout проекта:

```bash
DEPLOY_HOST=130.49.151.251 \
DEPLOY_DOMAIN=repire-status.ru \
scripts/deploy-production.sh
```

### 8. Резервные копии

Дамп PostgreSQL:

```bash
docker compose -p repaircrm-client exec -T postgres \
  pg_dump -U repaircrm_client repaircrm_client | gzip > backup_$(date +%Y%m%d).sql.gz
```

Восстановление:

```bash
gunzip -c backup_20260510.sql.gz | \
  docker compose -p repaircrm-client exec -T postgres \
    psql -U repaircrm_client repaircrm_client
```

### 9. Мониторинг

```bash
# Состояние контейнеров
docker compose -p repaircrm-client ps

# Health check
curl https://repire-status.ru/api/health

# Логи backend
docker compose -p repaircrm-client logs -f --tail=100 backend

# Логи nginx (хост)
tail -f /var/log/nginx/error.log
```

### Работа двух стеков на одном сервере

На продовом сервере оба приложения работают параллельно:

| Стек | Docker project | Порт (хост→контейнер) | Домен |
|------|---------------|----------------------|-------|
| Repair CRM | `repaircrm` | `8080:80` | `b00bs.ru` |
| Client Portal | `repaircrm-client` | `8081:80` | `repire-status.ru` |

Хостовый Nginx читает `/etc/nginx/sites-enabled/repaircrm-sites.conf` и
проксирует по `server_name`.
