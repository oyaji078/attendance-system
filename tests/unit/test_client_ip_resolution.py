"""Which address rate limits are counted against.

Behind a tunnel every request arrives from the proxy, so per-IP limits collapse
into one shared bucket unless the forwarded header is read — but reading it
unconditionally lets any client forge its own identity and bypass the limit.
Hence the opt-in switch, and these tests for both sides of it.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

pytest.importorskip("fastapi")

from app.core.rate_limiter import client_ip_for


class FakeRequest:
    def __init__(self, host: str | None, headers: dict[str, str] | None = None):
        self.client = SimpleNamespace(host=host) if host else None
        self.headers = headers or {}


@pytest.fixture
def trust(monkeypatch):
    def _set(enabled: bool):
        import app.core.config as config

        monkeypatch.setattr(
            config, "get_settings", lambda: SimpleNamespace(trust_proxy_headers=enabled)
        )

    return _set


def test_untrusted_ignores_a_forged_forwarded_header(trust):
    trust(False)
    request = FakeRequest("127.0.0.1", {"x-forwarded-for": "1.2.3.4"})
    # Off by default: a client could otherwise send a new value per request and
    # never hit the limit.
    assert client_ip_for(request) == "127.0.0.1"


def test_trusted_uses_the_first_forwarded_hop(trust):
    trust(True)
    request = FakeRequest("127.0.0.1", {"x-forwarded-for": "203.0.113.7, 10.0.0.1"})
    assert client_ip_for(request) == "203.0.113.7"


def test_trusted_falls_back_when_the_header_is_absent(trust):
    trust(True)
    assert client_ip_for(FakeRequest("10.1.1.1")) == "10.1.1.1"


def test_trusted_falls_back_when_the_header_is_blank(trust):
    trust(True)
    assert client_ip_for(FakeRequest("10.1.1.1", {"x-forwarded-for": "   "})) == "10.1.1.1"


def test_missing_client_is_never_a_crash(trust):
    trust(False)
    assert client_ip_for(FakeRequest(None)) == "unknown"
