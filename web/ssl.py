"""TLS context construction and certificate health helpers.

This module centralises the "how does the web server get its TLS"
decision so the rest of the code base does not need to care.  Three
valid deployments are supported (see ``docs/SSL.md`` for the full
decision tree):

* **TLS enabled** -- both ``SSL_CERT`` and ``SSL_KEY`` point at a real,
  matching cert/key pair.  Loaded into an :class:`ssl.SSLContext`.
* **Plain HTTP** -- neither ``SSL_CERT`` nor ``SSL_KEY`` is set.  The
  server runs in HTTP mode.  This is legitimate for LAN/dev deployments
  only: the operator must make sure the host is not internet-exposed.
* **Misconfig** -- exactly one of the two is set.  :func:`build_ssl_context`
  raises :class:`ConfigError`.  A server that *thinks* it is HTTPS but
  is actually HTTP is a much worse failure than a server that refuses
  to start, so the failure is loud and happens at boot.

Expiry handling
---------------

Expiry is *reported* (always), not silently enforced.  An expired or
about-to-expire certificate produces a ``warning``-level log at boot
so the condition is visible, and :func:`expiry_days_remaining` is the
stable helper recurring health checks must call to turn the same signal
into a hard alert.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional

from utils.logger import get_logger

logger = get_logger(__name__)

# Days below which we log a warning at boot.  30 days matches common
# Let's Encrypt guidance (certs valid 90 days, renew at 30) and gives
# the operator one full weekly cron cycle of buffer to act.
DEFAULT_EXPIRY_WARN_DAYS = 30


class ConfigError(RuntimeError):
    """Raised when TLS is half-configured (cert set without key, or vice versa)."""


@dataclass(frozen=True)
class SslConfig:
    """Resolved configuration the server will actually run with.

    Attributes:
        enabled: ``True`` when :attr:`context` is a usable TLS context.
        context: The :class:`ssl.SSLContext` for Flask, or ``None`` in
            plain-HTTP mode.
        cert_path: The path the active certificate was loaded from;
            ``None`` in plain-HTTP mode.
    """

    enabled: bool
    context: Optional["object"] = None
    cert_path: Optional[str] = None


def _parse_openssl_date(raw: str) -> datetime:
    """Parse ``openssl x509 -enddate`` output (``%b %d %H:%M:%S %Y %Z``)."""
    return datetime.strptime(raw, "%b %d %H:%M:%S %Y %Z").replace(tzinfo=timezone.utc)


def expiry_days_remaining(cert_path: Optional[str]) -> Optional[int]:
    """Return the whole days until the certificate at ``cert_path`` expires.

    Implemented with a single ``openssl x509 -enddate -noout`` subprocess
    call, which is available on every Ubuntu/Debian-style host and on the
    standard CI image (``ubuntu-latest`` ships ``openssl``).

    Args:
        cert_path: Filesystem path of a PEM certificate (a chain file is
            fine -- ``openssl x509`` reads the first/leaf one).

    Returns:
        Optional[int]: Whole days left (negative when expired).
        ``None`` when ``cert_path`` is ``None`` or the date could not be
        determined (caller should treat that as "unknown", not "fine").
    """
    if not cert_path:
        return None
    try:
        import subprocess

        result = subprocess.run(  # nosec B603 -- cert_path comes from our own env
            ["openssl", "x509", "-enddate", "-noout", "-in", cert_path],
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            logger.warning(
                "Could not read certificate expiry from %s: %s",
                cert_path,
                result.stderr.strip(),
            )
            return None
        for line in result.stdout.splitlines():
            if line.startswith("notAfter="):
                not_after = _parse_openssl_date(line.split("=", 1)[1].strip())
                now = datetime.now(timezone.utc)
                return int((not_after - now).total_seconds() // 86_400)
    except Exception as exc:  # noqa: BLE001 -- best-effort health check
        logger.warning(
            "Could not compute certificate expiry for %s: %s", cert_path, exc
        )
    return None


def log_expiry_status(
    cert_path: str, warn_days: int = DEFAULT_EXPIRY_WARN_DAYS
) -> None:
    """Log a warning if the certificate at ``cert_path`` is expired or near expiry.

    Intended to run once at server boot so an already-dead certificate is
    visible in the deployment logs.  Recurring enforcement (alerting,
    hard-failing) belongs in ``scripts/cert_health_check.sh`` and its
    cron entry -- not here, so a brief renewal hiccup does not take a
    service down mid-flight.

    Args:
        cert_path: Path of the active certificate.
        warn_days: Warn when fewer than this many days remain.
    """
    days = expiry_days_remaining(cert_path)
    if days is None:
        logger.warning(
            "TLS certificate expiry could not be determined from %s -- "
            "manually check openssl x509 -enddate.",
            cert_path,
        )
        return
    if days < 0:
        logger.warning(
            "TLS certificate at %s is EXPIRED (%d days ago). The server "
            "is running with a dead certificate -- browsers will reject "
            "the connection and renewal is needed immediately "
            "(see docs/SSL.md).",
            cert_path,
            -days,
        )
    elif days <= warn_days:
        logger.warning(
            "TLS certificate at %s expires in %d days (threshold %d) -- "
            "schedule renewal (see docs/SSL.md).",
            cert_path,
            days,
            warn_days,
        )
    else:
        logger.info("TLS certificate at %s valid for %d more days", cert_path, days)


def build_ssl_context(
    cert_path: Optional[str],
    key_path: Optional[str],
    warn_days: int = DEFAULT_EXPIRY_WARN_DAYS,
) -> SslConfig:
    """Build the :class:`SslConfig` for a given cert/key pair setting.

    Decision table::

        SSL_CERT  SSL_KEY   result
        --------  --------  ------------------------------------------------------
        (unset)   (unset)   SslConfig: plain HTTP, context None
        set       set       SslConfig: TLS on, context loaded, expiry checked
        set       (unset)   ConfigError -- loud failure at boot
        (unset)   set       ConfigError -- loud failure at boot

    Args:
        cert_path: Value of ``SSL_CERT`` (or ``None`` when unset).
        key_path: Value of ``SSL_KEY`` (or ``None`` when unset).
        warn_days: Threshold forwarded to :func:`log_expiry_status`.

    Returns:
        SslConfig: The resolved runtime TLS configuration.

    Raises:
        ConfigError: TLS is half-configured (exactly one of the two is set),
            or the cert/key paths are set but do not exist on disk.
        ssl.SSLError: The cert/key pair fails to load (mismatched pair,
            wrong format, passphrase-protected key).
    """
    import os
    import ssl

    # Narrow to the three valid/invalid shapes with simple linear checks
    # so the downstream code can assume whichever shape it is.
    if cert_path is None and key_path is None:
        # Plain-HTTP mode (Option A).  Legitimate for LAN/dev only.
        logger.warning(
            "SSL_CERT/SSL_KEY not set -- web server running over plain HTTP. "
            "Only do this if the host is NOT internet-exposed."
        )
        return SslConfig(enabled=False, context=None, cert_path=None)

    # At least one is set.  Exactly one = half-configured = loud failure.
    if cert_path is None or key_path is None:
        raise ConfigError(
            "Half-configured TLS: SSL_CERT and SSL_KEY must be set together, "
            "or both left unset for plain HTTP. "
            f"Got cert={cert_path!r}, key={key_path!r}. "
            "See docs/SSL.md for the intended three options."
        )

    # Here both are definitely str.
    cert = cert_path
    key = key_path
    for candidate in (cert, key):
        if not os.path.isfile(candidate):
            raise ConfigError(f"TLS file not found on disk: {candidate!r}")

    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    try:
        context.load_cert_chain(certfile=cert, keyfile=key)
    except ssl.SSLError as exc:
        raise ssl.SSLError(
            f"Failed to load TLS cert/key pair: cert={cert!r}, "
            f"key={key!r}. Confirm it is a matching pair, that the "
            f"CA chain is included in the cert file (Let's Encrypt "
            f'"fullchain.pem" style), and that the key has no passphrase. '
            f"Original error: {exc}"
        ) from exc

    log_expiry_status(cert, warn_days=warn_days)
    return SslConfig(enabled=True, context=context, cert_path=cert)
