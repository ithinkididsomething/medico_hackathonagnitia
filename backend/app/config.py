"""Environment-driven configuration for the backend.

All runtime settings come from environment variables, optionally loaded from
a `.env` file at the project root (see `.env.example`). Secrets live only in
`.env`, which is git-ignored.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

BACKEND_DIR = Path(__file__).resolve().parents[1]
PROJECT_ROOT = BACKEND_DIR.parent

# Root .env first, optional backend/.env can override it.
load_dotenv(PROJECT_ROOT / ".env")
load_dotenv(BACKEND_DIR / ".env", override=True)


def _env(name: str, default: str) -> str:
    value = os.environ.get(name)
    return value if value not in (None, "") else default


DEFAULT_SQLITE_PATH = BACKEND_DIR / "data" / "medico.db"


def _database_url() -> str:
    """SQLite by default; point DATABASE_URL at PostgreSQL/Supabase to switch.

    Supported: sqlite:///path, postgresql://user:pass@host/db, postgres://...
    """
    explicit = os.environ.get("DATABASE_URL")
    if explicit:
        return explicit
    path = Path(_env("DATABASE_PATH", str(DEFAULT_SQLITE_PATH))).expanduser()
    return f"sqlite:///{path.as_posix()}"


def sqlite_path_from_url(url: str) -> Path | None:
    """File path of a sqlite URL (None for server databases such as PostgreSQL)."""
    if url.startswith("sqlite:///"):
        return Path(url[len("sqlite:///"):])
    return None


def redact_database_url(url: str) -> str:
    """Hide credentials before a URL is logged or returned by the API."""
    if "@" in url and "://" in url:
        head, _, tail = url.partition("://")
        _, _, rest = tail.partition("@")
        return f"{head}://***@{rest}"
    return url


@dataclass(frozen=True)
class Settings:
    backend_host: str
    backend_port: int
    frontend_origin: str
    database_url: str
    geocoder_base_url: str
    router_base_url: str
    router_profile: str
    osm_tile_url: str
    user_agent: str
    routing_api_key: str  # never returned by any API endpoint

    @property
    def database_path(self) -> Path | None:
        """Local file path when using SQLite, else None (server database)."""
        return sqlite_path_from_url(self.database_url)


def get_settings() -> Settings:
    """Build settings fresh from the environment (so tests can patch env vars)."""
    return Settings(
        backend_host=_env("BACKEND_HOST", "127.0.0.1"),
        backend_port=int(_env("BACKEND_PORT", "8000")),
        frontend_origin=_env("FRONTEND_ORIGIN", "http://localhost:5173"),
        database_url=_database_url(),
        geocoder_base_url=_env(
            "GEOCODER_BASE_URL", "https://nominatim.openstreetmap.org"
        ).rstrip("/"),
        router_base_url=_env(
            "ROUTER_BASE_URL", "https://router.project-osrm.org"
        ).rstrip("/"),
        router_profile=_env("ROUTER_PROFILE", "driving"),
        osm_tile_url=_env(
            "OSM_TILE_URL", "https://tile.openstreetmap.org/{z}/{x}/{y}.png"
        ),
        user_agent=_env("USER_AGENT", "medico-dev/0.1 (local development)"),
        routing_api_key=_env("ROUTING_API_KEY", ""),
    )
