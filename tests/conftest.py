"""Shared pytest fixtures for the web security suite.

:mod:`tests.test_ssl` must not depend on pre-existing files in ``/tmp``
(CI runners are ephemeral), so this provides a session-scoped fixture
that generates the required self-signed cert/key pairs with ``openssl``.
"""

from __future__ import annotations

import subprocess
from typing import Any

import pytest


def _make_pair(base_dir: str, name: str, days: int) -> tuple[str, str]:
    """Create a self-signed cert+key pair at ``base_dir/<name>.(crt|key)``.

    Args:
        base_dir: Directory to write into (must exist).
        name: Uniquifying name (becomes the filename stem and the CN).
        days: Certificate lifetime in days from now.

    Returns:
        tuple[str, str]: ``(cert_path, key_path)``.

    Raises:
        RuntimeError: If ``openssl`` is missing or fails.
    """
    cert_path = f"{base_dir}/{name}.crt"
    key_path = f"{base_dir}/{name}.key"
    result = subprocess.run(
        [
            "openssl",
            "req",
            "-x509",
            "-newkey",
            "rsa:2048",
            "-keyout",
            key_path,
            "-out",
            cert_path,
            "-days",
            str(days),
            "-nodes",
            "-subj",
            f"/CN={name}.example",
        ],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(f"openssl failed: {result.stderr}")
    return cert_path, key_path


@pytest.fixture(scope="session")
def ssl_fixtures(tmp_path_factory: Any) -> dict[str, str]:
    """Generate the cert/key pairs the TLS tests need, once per session.

    Returns:
        dict[str, str]: Paths under keys ``valid_cert``, ``valid_key``,
        ``soon_cert``, ``soon_key`` (valid ~1 day, triggers the
        "expires soon" warning path), and ``mismatch_key`` (a valid key
        from a *different* pair, so a cert+key mismatch can be asserted).
    """
    base = str(tmp_path_factory.mktemp("ssl_fixtures"))
    valid_cert, valid_key = _make_pair(base, "validssl", days=400)
    soon_cert, soon_key = _make_pair(base, "soonssl", days=1)
    _, mismatch_key = _make_pair(base, "mismatchssl", days=400)
    return {
        "valid_cert": valid_cert,
        "valid_key": valid_key,
        "soon_cert": soon_cert,
        "soon_key": soon_key,
        "mismatch_key": mismatch_key,
    }
