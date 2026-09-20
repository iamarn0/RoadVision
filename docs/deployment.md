# Deployment

RoadVision is intended to run as five Compose services: `web`, `api`, `worker`, `postgres`, `redis`.

## Compose

```bash
docker compose up --build
```

- Persistent volumes for PostgreSQL and optional Redis AOF
- Bind or named volume for `storage/` and `models/`
- Health checks on API, Postgres, Redis
- Worker concurrency 1 unless you have proven VRAM headroom

GPU in containers is optional. Document NVIDIA Container Toolkit separately; laptops often run the **worker natively** for CUDA while other services stay in Docker.

## Migrations

```bash
docker compose exec api alembic upgrade head
```

Run before first traffic.

## Configuration

Inject `.env` via Compose `env_file`. Never bake secrets into images.

Required for production:

- `APP_ENV=production`
- `AUTH_DISABLED=false`
- Strong unique `SECRET_KEY` (not the placeholder)
- `BOOTSTRAP_ADMIN_EMAIL` / `BOOTSTRAP_ADMIN_PASSWORD` for first boot only
- `SESSION_COOKIE_SECURE=true` behind HTTPS
- Strict `API_CORS_ORIGINS` (prefer same-origin reverse proxy)

## Reverse proxy

Terminate TLS in front of `web` and `/api` on one origin so the session cookie is first-party. Do not expose PostgreSQL or Redis publicly. Hide OpenAPI (`/docs`) — it is already disabled when `APP_ENV=production`.

## Scaling

v0.1.0 assumes one inference worker. Horizontal worker scaling requires per-GPU device assignment and queue fairness; not the default laptop profile.

## Backups

- PostgreSQL dumps (include `users`, `sessions`, `audit_logs`)
- Object/files under `storage/`
- Model files (not in git)

## Limitations

Do not declare production-ready until quality gates are verified: services start, real inference, authenticated media access, retention, and recovery.
