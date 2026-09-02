"""Session cookie flags.

The documented way to demo this system is a public Cloudflare HTTPS tunnel while
APP_ENV is still "development". Deriving Secure from APP_ENV alone sent the
session cookie over that tunnel unprotected, so it follows the request scheme.
"""

from __future__ import annotations


def secure_cookie_for(scheme: str, forwarded_proto: str | None, app_env: str) -> bool:
    """Mirrors the decision in app.api.routes.auth.login."""
    proto = (forwarded_proto or "").split(",")[0].strip().lower()
    is_https = proto == "https" or scheme == "https"
    return is_https or app_env == "production"


def test_https_tunnel_in_development_still_gets_a_secure_cookie():
    # cloudflared terminates TLS and forwards over http with this header.
    assert secure_cookie_for("http", "https", "development") is True


def test_direct_https_gets_a_secure_cookie():
    assert secure_cookie_for("https", None, "development") is True


def test_production_is_always_secure():
    assert secure_cookie_for("http", None, "production") is True


def test_plain_localhost_development_stays_insecure_so_login_works():
    # Secure cookies are dropped by browsers on http://localhost origins, which
    # would break the normal dev loop.
    assert secure_cookie_for("http", None, "development") is False


def test_forwarded_proto_list_uses_the_first_hop():
    assert secure_cookie_for("http", "https, http", "development") is True
    assert secure_cookie_for("http", "http, https", "development") is False


def test_forwarded_proto_is_case_and_space_insensitive():
    assert secure_cookie_for("http", "  HTTPS  ", "development") is True
