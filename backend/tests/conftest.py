import os
import sys
import tempfile
from pathlib import Path

import pytest

# Make the `app` package importable when pytest runs from the backend folder.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

# Keep API tests off the developer's real database unless one is explicitly set.
if not os.environ.get("DATABASE_PATH"):
    os.environ["DATABASE_PATH"] = str(
        Path(tempfile.mkdtemp(prefix="medico-test-")) / "test.db"
    )

# Keep API tests off the live OSRM routing server: straight-line placeholder
# travel estimates are deterministic. Routing tests patch the provider or
# re-enable routing explicitly via monkeypatch.setenv.
os.environ.setdefault("ROUTING_ENABLED", "false")

from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402


@pytest.fixture()
def client():
    # `with` runs the app lifespan, which initializes the database schema.
    with TestClient(app) as test_client:
        # Referral records are per-test fixtures: clear them (and their audit
        # trail) so dashboard counts/filters start from a known empty state.
        from app.config import get_settings
        from app.db.connection import db_session

        with db_session(get_settings()) as connection:
            connection.execute("DELETE FROM referral_status_events")
            connection.execute("DELETE FROM referrals")
        yield test_client
