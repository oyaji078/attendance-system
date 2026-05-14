from __future__ import annotations

import pytest

pytest.importorskip("fastapi")

from fastapi import Depends, FastAPI, status
from fastapi.testclient import TestClient

from app.core.csrf import CsrfProtection, csrf_dependency
from app.core.dependencies import AppContainer


class FakeCsrfRedis:
    def __init__(self) -> None:
        self._store: dict[str, str] = {}

    async def get(self, key: str) -> str | None:
        return self._store.get(key)

    async def setex(self, key: str, ttl: int, value: str) -> None:
        self._store[key] = value

    async def delete(self, key: str) -> None:
        self._store.pop(key, None)


@pytest.fixture
def app() -> FastAPI:
    _app = FastAPI()

    @_app.get("/safe")
    async def safe() -> dict[str, str]:
        return {"status": "ok"}

    @_app.post("/unsafe")
    async def unsafe() -> dict[str, str]:
        return {"status": "ok"}

    @_app.patch("/unsafe-patch")
    async def unsafe_patch() -> dict[str, str]:
        return {"status": "ok"}

    _app.state.container = AppContainer(
        settings=None,
        engine=None,
        session_factory=None,
        object_storage=None,
        cache=None,
        pipeline=None,
        liveness_service=None,
        quality_gate=None,
        template_builder=None,
        csrf_protection=None,
    )
    return _app


def test_no_csrf_protection_when_not_configured(app: FastAPI) -> None:
    for route in app.router.routes:
        if hasattr(route, "dependencies"):
            route.dependencies = [Depends(csrf_dependency)]
    client = TestClient(app)
    resp = client.post("/unsafe")
    assert resp.status_code == 200


def test_safe_methods_skip_csrf(app: FastAPI) -> None:
    csrf = CsrfProtection(None, "test-secret", 3600)
    app.state.container.csrf_protection = csrf
    for route in app.router.routes:
        if hasattr(route, "dependencies"):
            route.dependencies = [Depends(csrf_dependency)]
    client = TestClient(app)
    resp = client.get("/safe")
    assert resp.status_code == 200


def _build_csrf_app(with_redis: bool = False) -> FastAPI:
    _app = FastAPI(dependencies=[Depends(csrf_dependency)])

    @_app.post("/admin/action")
    async def action() -> dict[str, str]:
        return {"status": "ok"}

    @_app.patch("/admin/user/deactivate")
    async def deactivate() -> dict[str, str]:
        return {"status": "ok"}

    @_app.patch("/admin/user/reactivate")
    async def reactivate() -> dict[str, str]:
        return {"status": "ok"}

    if with_redis:
        fake_redis = FakeCsrfRedis()
        csrf = CsrfProtection(fake_redis, "test-secret", 3600)  # type: ignore[arg-type]
        csrf._redis = fake_redis  # type: ignore[assignment]
    else:
        csrf = CsrfProtection(None, "test-secret", 3600)

    _app.state.container = AppContainer(
        settings=None,
        engine=None,
        session_factory=None,
        object_storage=None,
        cache=None,
        pipeline=None,
        liveness_service=None,
        quality_gate=None,
        template_builder=None,
        csrf_protection=csrf,
    )
    return _app


class TestCsrfLocalStore:
    def test_unsafe_without_csrf_header_returns_403(self) -> None:
        app = _build_csrf_app()
        client = TestClient(app)
        client.cookies.set("csrf_token", "valid-token")
        resp = client.post("/admin/action")
        assert resp.status_code == 403
        assert "CSRF" in resp.json()["detail"]

    def test_unsafe_without_csrf_cookie_returns_403(self) -> None:
        app = _build_csrf_app()
        client = TestClient(app)
        resp = client.post("/admin/action", headers={"x-csrf-token": "valid-token"})
        assert resp.status_code == 403
        assert "CSRF" in resp.json()["detail"]

    def test_mismatched_csrf_header_and_cookie_returns_403(self) -> None:
        app = _build_csrf_app()
        client = TestClient(app)
        client.cookies.set("csrf_token", "cookie-token")
        resp = client.post("/admin/action", headers={"x-csrf-token": "header-token"})
        assert resp.status_code == 403
        assert "CSRF" in resp.json()["detail"]

    @pytest.mark.asyncio
    async def test_valid_csrf_token_returns_200(self) -> None:
        app = _build_csrf_app()
        csrf: CsrfProtection = app.state.container.csrf_protection
        token = await csrf.generate_token()
        client = TestClient(app)
        client.cookies.set("csrf_token", token)
        resp = client.post("/admin/action", headers={"x-csrf-token": token})
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_same_csrf_token_reusable_for_multiple_requests(self) -> None:
        app = _build_csrf_app()
        csrf: CsrfProtection = app.state.container.csrf_protection
        token = await csrf.generate_token()
        client = TestClient(app)
        client.cookies.set("csrf_token", token)
        headers = {"x-csrf-token": token}

        for _ in range(3):
            resp = client.post("/admin/action", headers=headers)
            assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_deactivate_reactivate_with_same_token(self) -> None:
        app = _build_csrf_app()
        csrf: CsrfProtection = app.state.container.csrf_protection
        token = await csrf.generate_token()
        client = TestClient(app)
        client.cookies.set("csrf_token", token)
        headers = {"x-csrf-token": token}

        resp1 = client.patch("/admin/user/deactivate", headers=headers)
        assert resp1.status_code == 200

        resp2 = client.patch("/admin/user/reactivate", headers=headers)
        assert resp2.status_code == 200

        resp3 = client.patch("/admin/user/deactivate", headers=headers)
        assert resp3.status_code == 200

        resp4 = client.patch("/admin/user/reactivate", headers=headers)
        assert resp4.status_code == 200

    @pytest.mark.asyncio
    async def test_expired_token_returns_403(self) -> None:
        app = _build_csrf_app()
        csrf: CsrfProtection = app.state.container.csrf_protection
        csrf._ttl_seconds = -1
        expired = await csrf.generate_token()
        client = TestClient(app)
        client.cookies.set("csrf_token", expired)
        resp = client.post("/admin/action", headers={"x-csrf-token": expired})
        assert resp.status_code == 403
        assert "CSRF" in resp.json()["detail"]


class TestCsrfRedisStore:
    def test_redis_mismatched_csrf_returns_403(self) -> None:
        app = _build_csrf_app(with_redis=True)
        client = TestClient(app)
        client.cookies.set("csrf_token", "cookie-val")
        resp = client.post("/admin/action", headers={"x-csrf-token": "header-val"})
        assert resp.status_code == 403
        assert "CSRF" in resp.json()["detail"]

    @pytest.mark.asyncio
    async def test_redis_valid_csrf_token_returns_200(self) -> None:
        app = _build_csrf_app(with_redis=True)
        csrf: CsrfProtection = app.state.container.csrf_protection
        token = await csrf.generate_token()
        client = TestClient(app)
        client.cookies.set("csrf_token", token)
        resp = client.post("/admin/action", headers={"x-csrf-token": token})
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_redis_csrf_token_reusable(self) -> None:
        app = _build_csrf_app(with_redis=True)
        csrf: CsrfProtection = app.state.container.csrf_protection
        token = await csrf.generate_token()
        client = TestClient(app)
        client.cookies.set("csrf_token", token)
        headers = {"x-csrf-token": token}

        for _ in range(3):
            resp = client.post("/admin/action", headers=headers)
            assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_redis_deactivate_reactivate_with_same_token(self) -> None:
        app = _build_csrf_app(with_redis=True)
        csrf: CsrfProtection = app.state.container.csrf_protection
        token = await csrf.generate_token()
        client = TestClient(app)
        client.cookies.set("csrf_token", token)
        headers = {"x-csrf-token": token}

        resp1 = client.patch("/admin/user/deactivate", headers=headers)
        assert resp1.status_code == 200

        resp2 = client.patch("/admin/user/reactivate", headers=headers)
        assert resp2.status_code == 200

    @pytest.mark.asyncio
    async def test_redis_invalidate_removes_token(self) -> None:
        app = _build_csrf_app(with_redis=True)
        csrf: CsrfProtection = app.state.container.csrf_protection
        token = await csrf.generate_token()
        await csrf.invalidate_token(token)
        client = TestClient(app)
        client.cookies.set("csrf_token", token)
        resp = client.post("/admin/action", headers={"x-csrf-token": token})
        assert resp.status_code == 403
        assert "CSRF" in resp.json()["detail"]
