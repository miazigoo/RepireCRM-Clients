# Repair CRM Client Backend

Standalone backend for the customer portal. It stores customer accounts,
verified contacts, customer-visible order snapshots and pending actions for CRM
sync.

## Run

Docker is the default runtime for the full stack:

```bash
cp .env.example .env
make up
```

For local backend development:

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
alembic -c alembic.ini upgrade head
uvicorn app.main:app --reload --host 0.0.0.0 --port 8040
```

Runtime schema changes are managed by Alembic. The app no longer calls
`Base.metadata.create_all()` on startup.

## Auth Policy

Set `CLIENT_PORTAL_AUTH_POLICY` to one of:

- `phone_or_email`
- `phone_only`
- `email_only`

## Sync API

CRM requests to `/api/sync/*` must include:

```text
X-Sync-Token: <CLIENT_PORTAL_SYNC_API_KEY>
X-Tenant-Key: <CLIENT_PORTAL_TENANT_KEY>
```

Supported CRM endpoints:

- `POST /api/sync/orders/upsert`
- `GET /api/sync/actions?limit=100`
- `POST /api/sync/actions/{id}/mark-synced`

The background worker can trigger CRM sync runs when `CLIENT_PORTAL_CRM_BASE_URL`
and `CLIENT_PORTAL_CRM_API_KEY` are configured.

## Security

The API sends security headers including CSP, `X-Content-Type-Options`,
`X-Frame-Options`, referrer policy and permissions policy. User-controlled text
fields are stored as plain text after HTML/JS stripping to reduce stored XSS
risk before data reaches web or mobile clients.

## Mobile

Mobile clients use the same customer auth tokens plus:

- `POST /api/mobile/devices` to bind a device and push token;
- `GET /api/mobile/sessions` to show active refresh sessions;
- `POST /api/mobile/push/test` to queue a push notification for configured devices.
