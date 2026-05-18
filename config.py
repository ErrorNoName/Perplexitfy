"""Configuration and cookie storage for Perplexify."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

PROJECT_DIR = Path(__file__).resolve().parent
REPO_ROOT = Path(__file__).resolve().parents[3]
CORE_DIR = REPO_ROOT / "betbrain-core"
LOCAL_ENV_PATH = PROJECT_DIR / ".env"
LEGACY_ENV_PATH = CORE_DIR / ".env"
ENV_PATH = LOCAL_ENV_PATH
PRIVATE_COOKIE_PATH = PROJECT_DIR / "cookie.private.json"
COOKIE_ENV_KEY = "PPLX_COOKIE"


@dataclass(frozen=True)
class CookieState:
    cookie: str
    source: str

    @property
    def masked(self) -> str:
        if not self.cookie:
            return "(not configured)"
        return f"******** ({len(self.cookie)} chars)"


def ensure_import_paths() -> None:
    """Make direct script execution behave like ``python -m`` from repo root."""
    import sys

    for path in (REPO_ROOT, CORE_DIR):
        raw = str(path)
        if raw not in sys.path:
            sys.path.insert(0, raw)


def _parse_env_file(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    if not path.is_file():
        return values
    for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, _, value = stripped.partition("=")
        values[key.strip()] = value.strip()
    return values


def load_cookie() -> CookieState:
    env_cookie = os.getenv(COOKIE_ENV_KEY, "").strip()
    if env_cookie:
        return CookieState(env_cookie, "environment")

    for env_path in (LOCAL_ENV_PATH, LEGACY_ENV_PATH):
        env_values = _parse_env_file(env_path)
        file_cookie = env_values.get(COOKIE_ENV_KEY, "").strip()
        if file_cookie:
            os.environ.setdefault(COOKIE_ENV_KEY, file_cookie)
            return CookieState(file_cookie, str(env_path))

    private_cookie = _load_private_cookie()
    if private_cookie:
        os.environ.setdefault(COOKIE_ENV_KEY, private_cookie)
        return CookieState(private_cookie, str(PRIVATE_COOKIE_PATH))

    return CookieState("", "missing")


def save_cookie(cookie: str, *, mirror_env: bool = True) -> CookieState:
    clean = cookie.strip()
    if not clean:
        raise ValueError("Cookie is empty")
    _save_private_cookie(clean)
    os.environ[COOKIE_ENV_KEY] = clean
    if mirror_env:
        _upsert_env_value(COOKIE_ENV_KEY, clean)
    return CookieState(clean, str(PRIVATE_COOKIE_PATH))


def _load_private_cookie() -> str:
    if not PRIVATE_COOKIE_PATH.is_file():
        return ""
    try:
        data: dict[str, Any] = json.loads(
            PRIVATE_COOKIE_PATH.read_text(encoding="utf-8", errors="ignore")
        )
    except (json.JSONDecodeError, OSError):
        return ""
    return str(data.get(COOKIE_ENV_KEY) or data.get("cookie") or "").strip()


def _save_private_cookie(cookie: str) -> None:
    PRIVATE_COOKIE_PATH.write_text(
        json.dumps({COOKIE_ENV_KEY: cookie}, indent=2),
        encoding="utf-8",
    )


def _upsert_env_value(key: str, value: str) -> None:
    LOCAL_ENV_PATH.parent.mkdir(parents=True, exist_ok=True)
    lines = []
    found = False
    if LOCAL_ENV_PATH.is_file():
        lines = LOCAL_ENV_PATH.read_text(encoding="utf-8", errors="ignore").splitlines()

    updated: list[str] = []
    for line in lines:
        if line.strip().startswith(f"{key}="):
            updated.append(f"{key}={value}")
            found = True
        else:
            updated.append(line)
    if not found:
        if updated and updated[-1].strip():
            updated.append("")
        updated.append(f"{key}={value}")

    LOCAL_ENV_PATH.write_text("\n".join(updated) + "\n", encoding="utf-8")
