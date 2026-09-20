"""Password hashing helpers (Argon2)."""

from __future__ import annotations

import secrets
import string

from pwdlib import PasswordHash

_hasher = PasswordHash.recommended()

_ALPHABET = string.ascii_letters + string.digits


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return _hasher.verify(password, password_hash)
    except Exception:
        return False


def generate_temporary_password(length: int = 16) -> str:
    return "".join(secrets.choice(_ALPHABET) for _ in range(length))
