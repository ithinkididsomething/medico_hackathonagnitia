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

from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402


@pytest.fixture()
def client():
    # `with` runs the app lifespan, which initializes the database schema.
    with TestClient(app) as test_client:
        yield test_client
