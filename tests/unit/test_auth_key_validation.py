from __future__ import annotations

from app.core.security import is_secret_key_safe


def test_empty_auth_key_rejected() -> None:
    ok, msg = is_secret_key_safe("")
    assert not ok
    assert "empty" in msg.lower()


def test_placeholder_auth_keys_rejected() -> None:
    placeholders = [
        "CHANGE_ME_IN_PRODUCTION",
        "local-dev-attendance-secret-change-me",
        "dev-secret",
        "secret",
        "password",
    ]
    for key in placeholders:
        ok, msg = is_secret_key_safe(key)
        assert not ok, f"placeholder {key!r} should be rejected"
        assert "placeholder" in msg.lower()


def test_short_auth_key_rejected() -> None:
    ok, msg = is_secret_key_safe("short")
    assert not ok
    assert "at least 32 characters" in msg


def test_31_char_key_rejected() -> None:
    ok, msg = is_secret_key_safe("a" * 31)
    assert not ok
    assert "at least 32 characters" in msg


def test_valid_auth_key_accepted() -> None:
    ok, msg = is_secret_key_safe("a" * 32)
    assert ok
    assert msg == ""


def test_64_char_random_key_accepted() -> None:
    ok, msg = is_secret_key_safe("k" * 64)
    assert ok
    assert msg == ""


def test_case_insensitive_rejection() -> None:
    ok, msg = is_secret_key_safe("SECRET")
    assert not ok
    assert "placeholder" in msg.lower()
