"""Admin API must reject requests without a valid X-API-Key."""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.app.api.deps import get_db_session
from backend.app.api.v1 import admin
from backend.app.config import Settings


class _EmptyQuery:
    def options(self, *a, **k):
        return self

    def filter(self, *a, **k):
        return self

    def join(self, *a, **k):
        return self

    def order_by(self, *a, **k):
        return self

    def limit(self, *a, **k):
        return self

    def distinct(self, *a, **k):
        return self

    def all(self):
        return []


class _FakeSession:
    def query(self, *a, **k):
        return _EmptyQuery()


@pytest.fixture
def client_with(monkeypatch):
    def make(**settings):
        monkeypatch.setattr(
            "backend.app.api.deps.get_settings", lambda: Settings(_env_file=None, **settings)
        )
        app = FastAPI()
        app.include_router(admin.router, prefix="/v1")
        app.dependency_overrides[get_db_session] = lambda: _FakeSession()
        return TestClient(app)

    return make


def test_admin_disabled_without_configured_key(client_with):
    client = client_with(admin_api_key="", webhook_api_key="")
    assert client.get("/v1/admin/open-bets").status_code == 503


def test_admin_rejects_missing_or_wrong_key(client_with):
    client = client_with(admin_api_key="s3cret")
    assert client.get("/v1/admin/open-bets").status_code == 401
    assert client.get("/v1/admin/open-bets", headers={"X-API-Key": "nope"}).status_code == 401
    r = client.post("/v1/admin/bankroll/adjust", json={"amount": 100}, headers={"X-API-Key": "nope"})
    assert r.status_code == 401


def test_admin_accepts_correct_key(client_with):
    client = client_with(admin_api_key="s3cret")
    assert client.get("/v1/admin/open-bets", headers={"X-API-Key": "s3cret"}).status_code == 200


def test_admin_falls_back_to_webhook_key(client_with):
    client = client_with(admin_api_key="", webhook_api_key="hook")
    assert client.get("/v1/admin/open-bets", headers={"X-API-Key": "hook"}).status_code == 200
