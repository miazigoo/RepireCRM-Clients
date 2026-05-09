# Client Portal Architecture

`RepireCRM-Client` is a separate customer-facing product: frontend, backend,
customer auth, customer profile, local order cache and CRM sync API live here.
The worker CRM remains a separate system.

## Layout

- `frontend/`: Angular customer portal.
- `backend/`: FastAPI API, Alembic migrations, sync worker and tests.
- `docker/`: runtime Dockerfiles and nginx config.

## Responsibilities

- Customer accounts and passwords.
- Registration by phone, email, or either contact depending on company settings.
- Verified phone/email identities attached to one customer account.
- Password recovery through verified phone/email.
- Customer-visible order cache, stages and approvals.
- Customer-created repair requests and approval decisions as pending actions for CRM.
- Public settings endpoint for company branding and frontend feature flags.

## Auth Policies

`CLIENT_PORTAL_AUTH_POLICY` controls registration and login:

- `phone_or_email`: a customer may register and log in with phone or email.
- `phone_only`: phone is required, email can be added later in profile.
- `email_only`: email is required, phone can be added later in profile.

Orders are linked to customers by verified identities. When CRM syncs an order
with customer phone/email, the portal links it to an account that has the same
verified normalized phone/email.

## CRM Sync

The worker CRM talks to `/api/sync/*` with `X-Sync-Token`.

- CRM pushes order snapshots to `POST /api/sync/orders/upsert`.
- Portal exposes pending customer actions through `GET /api/sync/actions`.
- CRM marks handled actions with `POST /api/sync/actions/{id}/mark-synced`.

This avoids direct database sharing and keeps worker-only data outside the
client service.

## Branding

Frontend calls `GET /api/portal/settings` before rendering auth forms. The
settings response includes brand name, accent color, support contacts and
enabled auth policy. Per-company visual differences should be configured here
or provided as deployment assets, not implemented as a theme switcher in the UI.

## Web Security

Frontend templates avoid unsafe HTML rendering APIs. The backend stores
customer-controlled text as sanitized plain text, and both API/nginx responses
set CSP, frame, MIME-sniffing, referrer and permissions headers. Production TLS
termination should still add HSTS at the external nginx/edge layer.
