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
- защита от XSS/JS-инъекций через CSP/security headers и очистку текстовых полей.

## Структура

- `frontend/` - Angular клиентский кабинет.
- `backend/` - FastAPI API, миграции, sync-worker и тесты.
- `docker/` - nginx/backend Dockerfile и runtime-конфиги.

## Запуск в Docker

Весь продовый контур поднимается контейнерами: Postgres, backend, sync-worker и nginx
со статикой frontend.

```bash
cp .env.example .env
make up
```

По умолчанию nginx доступен на <http://127.0.0.1:4300>, backend - на
<http://127.0.0.1:8040>, Postgres публикуется на `127.0.0.1:55440`.

Основные команды:

```bash
make build
make test
make migrate
make logs
make down
```

Для production сначала сгенерируйте секреты:

```bash
make generate-secrets
cp .env.production.example .env
```

В production нельзя оставлять dev-ключи, `CLIENT_PORTAL_DELIVERY_DEBUG=true` и
широкий `CLIENT_PORTAL_CORS_ORIGINS=*`.

## Локальный frontend

```bash
cd frontend
npm install
npm run start:dev
```

По умолчанию frontend dev-сервер работает на <http://127.0.0.1:4300>, а `/api`
проксируется на клиентский backend `http://127.0.0.1:8040`. Другой backend можно указать так:

```bash
cd frontend
API_TARGET=http://127.0.0.1:8041 npm run start:dev
```

Backend запускается отдельно:

```bash
cd backend
source .venv/bin/activate
alembic -c alembic.ini upgrade head
uvicorn app.main:app --reload --host 0.0.0.0 --port 8040
```

## Проверка

```bash
backend/.venv/bin/pytest backend/tests
cd frontend
npm run build
npm run test:ci
```
