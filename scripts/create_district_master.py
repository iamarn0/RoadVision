"""Create a district master account. This is the only supported way to grant that role."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
API_ROOT = REPO_ROOT / "services" / "api"
for path in (str(REPO_ROOT), str(API_ROOT)):
    if path not in sys.path:
        sys.path.insert(0, path)

from sqlalchemy import select  # noqa: E402

from app.config import get_settings  # noqa: E402
from app.database.session import get_engine, get_session_factory  # noqa: E402
from app.models import Base  # noqa: E402
from app.security.districts import seed_west_bengal_districts  # noqa: E402
from app.security.passwords import hash_password  # noqa: E402
from packages.db.enums import UserRole  # noqa: E402
from packages.db.models import District, User, UserDistrict  # noqa: E402


def _parse_districts(raw: str) -> list[str]:
    names = [part.strip() for part in raw.split(",") if part.strip()]
    if not names:
        raise SystemExit("Provide at least one district name.")
    return names


def _is_sqlite(url: str) -> bool:
    return url.startswith("sqlite")


def _require_target_database(target: str, url: str) -> None:
    sqlite = _is_sqlite(url)
    if target == "local" and not sqlite:
        raise SystemExit(
            "Local target must use SQLite.\n"
            f"Current DATABASE_URL is PostgreSQL: {url}\n"
            "For localhost, set DATABASE_URL=sqlite:///./storage/roadvision.db in .env "
            "(or omit it — that is the default), then rerun with --target local."
        )
    if target == "production" and sqlite:
        raise SystemExit(
            "Production target must use PostgreSQL, not SQLite.\n"
            f"Current DATABASE_URL: {url}\n"
            "On the VPS run this inside the API container so it uses the Compose Postgres URL:\n"
            "  docker compose -f docker-compose.prod.yml exec api python /app/scripts/create_district_master.py --target production ..."
        )


def main() -> None:
    parser = argparse.ArgumentParser(description="Create or appoint a district master via developer script.")
    parser.add_argument(
        "--target",
        required=True,
        choices=("local", "production"),
        help="local = SQLite on this machine; production = PostgreSQL used by the deployed API",
    )
    parser.add_argument("--email", required=True)
    parser.add_argument("--name", required=True)
    parser.add_argument("--password", required=True)
    parser.add_argument("--districts", required=True, help="Comma-separated West Bengal district names")
    args = parser.parse_args()

    settings = get_settings()
    db_url = settings.resolved_database_url
    _require_target_database(args.target, db_url)
    kind = "SQLite" if _is_sqlite(db_url) else "PostgreSQL"
    print(f"Target: {args.target}")
    print(f"Database ({kind}): {db_url}")
    engine = get_engine()
    Base.metadata.create_all(bind=engine)
    factory = get_session_factory()
    db = factory()
    try:
        seed_west_bengal_districts(db)
        wanted = _parse_districts(args.districts)
        catalog = {row.name.lower(): row for row in db.scalars(select(District)).all()}
        missing = [name for name in wanted if name.lower() not in catalog]
        if missing:
            known = ", ".join(sorted(row.name for row in catalog.values()))
            raise SystemExit(f"Unknown district(s): {', '.join(missing)}\nKnown districts: {known}")

        email = args.email.lower().strip()
        user = db.scalar(select(User).where(User.email == email))
        if user and user.role != UserRole.DISTRICT_MASTER.value:
            raise SystemExit(
                f"A {user.role} account already exists for {email}. "
                "Refusing to change that account into a district master."
            )
        if user is None:
            user = User(
                email=email,
                display_name=args.name.strip(),
                password_hash=hash_password(args.password),
                role=UserRole.DISTRICT_MASTER.value,
                is_active=True,
                must_change_password=False,
            )
            db.add(user)
            db.flush()
            created = True
        else:
            user.display_name = args.name.strip()
            user.password_hash = hash_password(args.password)
            user.is_active = True
            created = False

        current = set(db.scalars(select(UserDistrict.district_id).where(UserDistrict.user_id == user.id)).all())
        added: list[str] = []
        for name in wanted:
            district = catalog[name.lower()]
            if district.id in current:
                continue
            db.add(UserDistrict(user_id=user.id, district_id=district.id))
            added.append(district.name)
        db.commit()
        action = "Created" if created else "Updated"
        appointed = ", ".join(wanted)
        extra = f" Newly appointed: {', '.join(added)}." if added else " District appointments were already present."
        print(f"{action} district master {email} ({user.display_name}). Appointed districts: {appointed}.{extra}")
        print(f"Done. Log in with {email} against this {kind} database.")
    finally:
        db.close()


if __name__ == "__main__":
    main()
