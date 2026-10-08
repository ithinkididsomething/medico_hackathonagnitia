import pytest

from app.config import get_settings
from app.db import connection, repository


@pytest.fixture()
def db_settings(tmp_path, monkeypatch):
    """Point the database at a temporary file for each test."""
    monkeypatch.setenv("DATABASE_PATH", str(tmp_path / "test.db"))
    settings = get_settings()
    connection.init_db(settings)
    return settings


def test_init_db_creates_file(db_settings):
    assert db_settings.database_path.exists()
    ok, error = connection.ping(db_settings)
    assert ok and error is None


def test_location_crud_roundtrip(db_settings):
    created = repository.create_location(
        name="Clinic A",
        latitude=28.6139,
        longitude=77.2090,
        address="New Delhi",
        settings=db_settings,
    )
    assert created["name"] == "Clinic A"
    assert created["latitude"] == 28.6139

    fetched = repository.get_location(created["id"], db_settings)
    assert fetched == created

    all_locations = repository.list_locations(db_settings)
    assert [loc["id"] for loc in all_locations] == [created["id"]]

    assert repository.delete_location(created["id"], db_settings) is True
    assert repository.get_location(created["id"], db_settings) is None
    assert repository.delete_location(created["id"], db_settings) is False
