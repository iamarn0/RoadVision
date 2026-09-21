# Versioning and releases

RoadVision uses one product version for the whole monorepo (API, worker, and web).

**Source of truth:** the root [`VERSION`](../VERSION) file (`MAJOR.MINOR.PATCH`, no `v` prefix).

Do not treat `APP_VERSION` in `.env` as the product version. Production restores `.env` from a backup that may contain a stale `APP_VERSION`; the running app reads `VERSION` instead.

## What MAJOR.MINOR.PATCH means

| Bump | When | Example |
| --- | --- | --- |
| **PATCH** | Bug fixes and small backward-compatible fixes | `0.1.0` → `0.1.1` |
| **MINOR** | New backward-compatible features | `0.1.1` → `0.2.0` |
| **MAJOR** | Breaking changes | `0.9.0` → `1.0.0` |

A version is an **intentional release**, not every commit on `main`.

## Deployment vs release

**Deployment** happens on every push (or merge) to `main` via [`.github/workflows/deploy.yml`](../.github/workflows/deploy.yml):

1. GitHub Actions SSHs into the Hostinger VPS
2. `cd /opt/roadvision`
3. `git fetch origin` and `git reset --hard origin/main`
4. Restore production `.env` from `/root/roadvision.env.bak`
5. Export `GIT_COMMIT` (short SHA)
6. `docker compose -f docker-compose.prod.yml up -d --build`
7. `alembic upgrade head`

Normal development:

```bash
git commit
git push origin main
```

That still deploys. It does **not** bump `VERSION`, create a Git tag, or open a GitHub Release.

**Release** is a separate, manual workflow ([`.github/workflows/release.yml`](../.github/workflows/release.yml)). It bumps `VERSION`, commits, tags `vX.Y.Z`, and creates a GitHub Release. That commit on `main` then deploys like any other push.

## Pull request tests

[`.github/workflows/ci.yml`](../.github/workflows/ci.yml) runs on pull requests targeting `main`:

- `api-tests` — `pytest` in `services/api`
- `worker-tests` — `pytest` in `services/worker`
- `web-tests` — `npm test` in `apps/web`

CI does **not** run inside `deploy.yml` and does not SSH to the VPS.

To make the gate mandatory in GitHub:

1. Repository **Settings → Branches**
2. Add a ruleset or classic protection rule for `main`
3. Enable **Require a pull request before merging**
4. Enable **Require status checks to pass before merging**
5. After the first CI run, select `api-tests`, `worker-tests`, and `web-tests`
6. Do **not** require the Deploy workflow (it only runs after merge)

Until that ruleset is on, CI is advisory. A direct push to `main` still deploys.

## How to create a release

GitHub → **Actions → Release → Run workflow**. Choose:

- **patch** — `x.y.z` → `x.y.(z+1)`
- **minor** — `x.y.z` → `x.(y+1).0`
- **major** — `x.y.z` → `(x+1).0.0`

The workflow:

1. Checks out `main`
2. Runs `python scripts/bump_version.py <patch|minor|major>`
3. Commits `VERSION` (`chore: release vX.Y.Z`)
4. Creates annotated tag `vX.Y.Z` on that commit
5. Pushes the commit and tag to `main`
6. Creates a GitHub Release titled `RoadVision vX.Y.Z` with generated notes

Application version in code and `/api/version` is `X.Y.Z` (no `v`). The Git tag and GitHub Release use `vX.Y.Z`.

Local equivalent (only if you are not using the workflow):

```bash
python scripts/bump_version.py patch
git add VERSION
git commit -m "chore: release v0.1.1"
git tag -a v0.1.1 -m "RoadVision v0.1.1"
git push origin main --follow-tags
```

Prefer the GitHub Action so the Release is created the same way every time.

## Git tags

Official releases use tags of the form `v0.1.0`, `v0.1.1`, `v0.2.0`, `v1.0.0`. The tag points at the version-bump commit. Ordinary development commits are not tagged.

## How to check the production version

Public endpoint (no secrets):

```bash
curl https://unikorncam.tech/api/version
```

Example:

```json
{
  "name": "RoadVision",
  "version": "0.2.0",
  "commit": "8f31a2c",
  "environment": "production"
}
```

In the app, **Settings** shows version, commit, and environment. The sidebar version label uses the same API.

`commit` is a short Git SHA. After this change is deployed, it is set from `GIT_COMMIT` during `deploy.yml`. Until that deploy has run, it may be `"unknown"`.

## Rollback to a tagged release

Checking out a tag **on the VPS only** is temporary. The next push to `main` runs `git reset --hard origin/main` and overwrites it.

Lasting rollback: put the tagged commit back on `main` (revert or reset, then push), so the existing deploy workflow lands that code. Treat a force-push to `main` as exceptional and coordinate it.

Example of a temporary VPS checkout (overwritten on the next `main` deploy):

```bash
cd /opt/roadvision
git fetch --tags origin
git checkout v0.1.0
cp /root/roadvision.env.bak .env
export GIT_COMMIT=$(git rev-parse --short HEAD)
docker compose -f docker-compose.prod.yml up -d --build
docker compose -f docker-compose.prod.yml exec -T api alembic upgrade head || true
```

## GitHub permissions and secrets

- **No new secrets.** Deploy still uses `VPS_HOST`, `VPS_USER`, `VPS_SSH_KEY`.
- Release uses `GITHUB_TOKEN` with `contents: write`.
- If **Actions workflow permissions** are read-only, set them to **Read and write** (Settings → Actions → General).
- If `main` is protected and GitHub Actions cannot push, allow the `github-actions` actor to push version commits, or use a PAT stored as a secret later. The workflows in this repo do not add a PAT by default.
