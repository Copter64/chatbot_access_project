"""Unifi UDM Pro API client.

Handles authentication and low-level HTTP communication with the
Unifi OS / UniFi Network application REST API.

The UDM Pro uses cookie-based auth:
  POST /api/auth/login  →  sets TOKEN cookie + X-CSRF-Token header
  All modifying requests must include X-CSRF-Token.
"""

import threading
from typing import Optional

import requests
import urllib3

from utils.logger import get_logger

logger = get_logger(__name__)


class UnifiAPIError(Exception):
    """Base exception for all Unifi API errors."""


class UnifiAuthError(UnifiAPIError):
    """Raised when Unifi authentication fails."""


class UnifiClient:
    """HTTP client for the Unifi UDM Pro REST API.

    Manages a persistent requests.Session, handles login, CSRF token
    rotation, and single-retry re-authentication on 401 responses.
    Thread-safe: a threading.Lock serialises re-authentication so only
    one Flask worker thread triggers a login call at a time.

    Args:
        host: Base URL of the UDM Pro, e.g. ``https://192.168.1.1``.
        username: Unifi local account username.
        password: Unifi local account password.
        site: Unifi site name (default ``"default"``).
        verify_ssl: Whether to verify the UDM Pro TLS certificate.
    """

    def __init__(
        self,
        host: str,
        username: str,
        password: str,
        site: str = "default",
        verify_ssl: bool = True,
    ) -> None:
        """Initialise client without connecting."""
        self.base_url = host.rstrip("/")
        self.username = username
        self.password = password
        self.site = site
        self.verify_ssl = verify_ssl

        self._session: requests.Session = requests.Session()
        self._session.verify = verify_ssl
        self._csrf_token: Optional[str] = None
        self._authenticated: bool = False
        self._lock = threading.Lock()

        if not verify_ssl:
            # Suppress InsecureRequestWarning when SSL verification is off
            urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
            logger.warning(
                "SSL verification is DISABLED for Unifi API — "
                "set UNIFI_VERIFY_SSL=true in production"
            )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def login(self) -> None:
        """Authenticate against the UDM Pro and store the session token.

        Raises:
            UnifiAuthError: If the credentials are rejected (HTTP 4xx).
            UnifiAPIError: On any network or unexpected HTTP error.
        """
        logger.info(f"Authenticating with Unifi at {self.base_url}")
        try:
            resp = self._session.post(
                f"{self.base_url}/api/auth/login",
                json={
                    "username": self.username,
                    "password": self.password,
                    "remember": True,
                },
                timeout=10,
            )
        except requests.RequestException as exc:
            raise UnifiAPIError(f"Login request failed: {exc}") from exc

        if resp.status_code in (401, 403):
            raise UnifiAuthError(
                f"Unifi login rejected (HTTP {resp.status_code}) — "
                "check UNIFI_USERNAME / UNIFI_PASSWORD"
            )

        try:
            resp.raise_for_status()
        except requests.HTTPError as exc:
            raise UnifiAPIError(f"Login HTTP error: {exc}") from exc

        self._csrf_token = resp.headers.get("X-CSRF-Token")
        self._authenticated = True
        logger.info("✅ Unifi authentication successful")

    def request(
        self,
        method: str,
        path: str,
        **kwargs,
    ) -> requests.Response:
        """Execute an authenticated API request.

        Ensures the client is logged in before the first call.  On a
        401 response the client re-authenticates once and retries.

        Args:
            method: HTTP method (``"GET"``, ``"PUT"``, etc.).
            path: URL path relative to ``base_url``.
            **kwargs: Forwarded to ``requests.Session.request``.

        Returns:
            requests.Response: The API response.

        Raises:
            UnifiAuthError: If re-authentication fails.
            UnifiAPIError: On network errors or unexpected HTTP errors.
        """
        # Lazy first-time login
        if not self._authenticated:
            with self._lock:
                if not self._authenticated:
                    self.login()

        resp = self._do_request(method, path, **kwargs)

        if resp.status_code == 401:
            logger.warning("Unifi session expired — re-authenticating")
            with self._lock:
                self.login()
            resp = self._do_request(method, path, **kwargs)

        try:
            resp.raise_for_status()
        except requests.HTTPError as exc:
            raise UnifiAPIError(
                f"Unifi API {method} {path} returned HTTP {resp.status_code}: " f"{exc}"
            ) from exc

        return resp

    def is_authenticated(self) -> bool:
        """Return True if a successful login has been completed."""
        return self._authenticated

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _do_request(
        self,
        method: str,
        path: str,
        **kwargs,
    ) -> requests.Response:
        """Issue a single HTTP request, injecting the CSRF token header.

        Args:
            method: HTTP method string.
            path: URL path relative to ``base_url``.
            **kwargs: Forwarded to ``requests.Session.request``.

        Returns:
            requests.Response: Raw response (status not checked).

        Raises:
            UnifiAPIError: On a network-level error.
        """
        url = f"{self.base_url}{path}"
        headers = dict(kwargs.pop("headers", {}))

        if self._csrf_token:
            headers["X-CSRF-Token"] = self._csrf_token

        try:
            return self._session.request(
                method,
                url,
                headers=headers,
                timeout=10,
                **kwargs,
            )
        except requests.RequestException as exc:
            raise UnifiAPIError(f"Network error during {method} {path}: {exc}") from exc
