"""Tests for web/ssl.py -- TLS context construction and certificate health.

The cert/key pairs are generated per-session by the ``ssl_fixtures``
fixture in :file:`tests/conftest.py` (so no ``/tmp`` state leaks in from
a prior run, and CI does not need pre-provisioned files).
"""

import logging
import ssl

import pytest

from web.ssl import ConfigError, SslConfig, build_ssl_context, expiry_days_remaining


class TestPlainHttpMode:
    """Option A: both SSL_CERT and SSL_KEY unset -> plain HTTP, no context."""

    def test_returns_disabled_config(self):
        cfg = build_ssl_context(None, None)
        assert isinstance(cfg, SslConfig)
        assert cfg.enabled is False
        assert cfg.context is None
        assert cfg.cert_path is None

    def test_does_not_raise(self):
        # Plain HTTP is a legitimate configuration -- must not raise.
        build_ssl_context(None, None)


class TestTlsMode:
    """Both set, matching pair -> TLS on, context loaded."""

    def test_loads_matching_pair(self, ssl_fixtures):
        cfg = build_ssl_context(ssl_fixtures["valid_cert"], ssl_fixtures["valid_key"])
        assert cfg.enabled is True
        assert cfg.cert_path == ssl_fixtures["valid_cert"]
        assert isinstance(cfg.context, ssl.SSLContext)

    def test_expiry_reported_for_valid_cert(self, ssl_fixtures):
        days = expiry_days_remaining(ssl_fixtures["valid_cert"])
        assert days is not None
        # Fixture was issued with -days 400.
        assert days >= 395

    def test_soon_to_expire_cert_triggers_warning_but_still_loads(
        self, ssl_fixtures, caplog
    ):
        # The documented contract: a cert within the warning window LOADS
        # (so a renewal hiccup does not kill the service) but WARNs.
        with caplog.at_level(logging.WARNING, logger="web.ssl"):
            cfg = build_ssl_context(
                ssl_fixtures["soon_cert"], ssl_fixtures["soon_key"], warn_days=30
            )
        assert cfg.enabled is True
        assert cfg.context is not None
        assert [r for r in caplog.records if r.levelno >= logging.WARNING]

    def test_mismatched_cert_and_key_raises_sslerror(self, ssl_fixtures):
        # valid_cert paired with a DIFFERENT pair's key must fail to load.
        with pytest.raises(ssl.SSLError):
            build_ssl_context(ssl_fixtures["valid_cert"], ssl_fixtures["mismatch_key"])


class TestHalfConfigured:
    """Exactly one of the two set -> loud ConfigError (fails boot on purpose)."""

    def test_cert_set_key_unset_raises(self, ssl_fixtures):
        with pytest.raises(ConfigError) as exc:
            build_ssl_context(ssl_fixtures["valid_cert"], None)
        assert "Half-configured TLS" in str(exc.value)

    def test_key_set_cert_unset_raises(self, ssl_fixtures):
        with pytest.raises(ConfigError) as exc:
            build_ssl_context(None, ssl_fixtures["valid_key"])
        assert "Half-configured TLS" in str(exc.value)


class TestMissingFiles:
    """Both set, but a file path does not exist -> loud ConfigError."""

    def test_cert_path_missing(self, ssl_fixtures):
        with pytest.raises(ConfigError) as exc:
            build_ssl_context("/nonexistent/fullchain.pem", ssl_fixtures["valid_key"])
        assert "not found on disk" in str(exc.value)

    def test_key_path_missing(self, ssl_fixtures):
        with pytest.raises(ConfigError) as exc:
            build_ssl_context(ssl_fixtures["valid_cert"], "/nonexistent/privkey.pem")
        assert "not found on disk" in str(exc.value)


class TestExpiryHelper:
    """expiry_days_remaining edge cases."""

    def test_none_input_returns_none(self):
        assert expiry_days_remaining(None) is None

    def test_missing_file_returns_none(self):
        # Reported as "unknown" (None), never a crash.
        assert expiry_days_remaining("/nonexistent/cert.pem") is None
