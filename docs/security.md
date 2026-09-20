# Security and privacy

License plate data can identify vehicle movements. Treat uploads and detections as sensitive.

## Configuration

- Secrets only in environment variables
- `SECRET_KEY` must be changed before any shared or production deployment
- CORS allow-list via `API_CORS_ORIGINS` (credentials enabled for the web origin)
- Production refuses to start if `AUTH_DISABLED=true` or `SECRET_KEY` is still the placeholder

## Authentication

- HttpOnly session cookie (`roadvision_session` by default); tokens are stored hashed server-side
- Passwords hashed with Argon2
- Authorized personnel only — administrators issue console access from **Personnel** (no public signup)
- Initial password is set by the administrator when access is issued (shown once to copy)
- First admin bootstrapped from `BOOTSTRAP_ADMIN_EMAIL` / `BOOTSTRAP_ADMIN_PASSWORD` when the user table is empty
- Login rate limiting (per IP and email)

## Access control (RBAC)

| Role | Label | Capabilities |
| --- | --- | --- |
| `admin` | Administrator | Full access, personnel management, video delete |
| `operator` | Operator | Upload, process, cancel/retry, export, read |
| `auditor` | Auditor | Read-only (dashboard, videos, jobs, detections, media, exports) |

All `/api/*` routes and `/ws/jobs/{job_id}` require a valid session except public `POST /api/auth/login`. `/health/live` remains unauthenticated for load balancers.

## Audit log

Actions recorded include login success/failure, logout, user create/update, password reset, session revoke, video upload/delete, job start, and export create.

## Upload hardening

- Untrusted files: never executed
- Safe stored names (UUID keys), original filename stored as metadata only
- Path traversal rejected
- Extension and MIME allow-lists
- Size cap (`MAX_UPLOAD_BYTES`)
- Decodability check before job processing
- Storage abstraction; API never returns absolute filesystem paths

## Rate limiting

Login attempts are rate-limited. Upload and export abuse protection can be extended similarly.

## Errors

Structured `error_code` values. Safe messages for users. Stack traces in logs only.

Auth-related codes: `UNAUTHENTICATED`, `FORBIDDEN`, `INVALID_CREDENTIALS`, `ACCOUNT_DISABLED`, `PASSWORD_CHANGE_REQUIRED`, `RATE_LIMITED`.

## Privacy controls

- `RETENTION_DAYS` (default 30) for videos, evidence, and exports
- Deletion must remove DB rows and storage objects
- No public unauthenticated detection APIs in production

## Retention, evidence, deletion

Operators should assume:

- Original video, annotated video, and crops are retained until policy expiry or explicit delete
- Audit logs may be retained longer than evidence (configurable later)
- Exports are also retention-scoped
