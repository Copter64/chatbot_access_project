"""Tests for unifi_modules.client.UnifiClient."""

from unittest.mock import MagicMock, patch

import pytest
import requests

from unifi_modules.client import UnifiAPIError, UnifiAuthError, UnifiClient


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_client(**kwargs) -> UnifiClient:
    """Return a client pointed at a fake host with SSL verification off."""
    defaults = dict(
        host="https://192.168.1.1",
        username="admin",
        password="secret",
        site="default",
        verify_ssl=False,
    )
    defaults.update(kwargs)
    return UnifiClient(**defaults)


def _mock_response(status_code: int = 200, json_data=None, headers=None):
    """Build a mock requests.Response."""
    resp = MagicMock(spec=requests.Response)
    resp.status_code = status_code
    resp.headers = headers or {}
    resp.json.return_value = json_data or {}
    if status_code >= 400:
        resp.raise_for_status.side_effect = requests.HTTPError(
            response=resp
        )
    else:
        resp.raise_for_status.return_value = None
    return resp


# ---------------------------------------------------------------------------
# login()
# ---------------------------------------------------------------------------


class TestLogin:
    """Tests for UnifiClient.login()."""

    def test_login_success_sets_authenticated(self):
        """Successful login marks client as authenticated."""
        client = _make_client()
        login_resp = _mock_response(
            200, headers={"X-CSRF-Token": "csrf-abc"}
        )
        with patch.object(client._session, "post", return_value=login_resp):
            client.login()

        assert client.is_authenticated()

    def test_login_stores_csrf_token(self):
        """CSRF token from response header is stored for future requests."""
        client = _make_client()
        login_resp = _mock_response(
            200, headers={"X-CSRF-Token": "token-xyz"}
        )
        with patch.object(client._session, "post", return_value=login_resp):
            client.login()

        assert client._csrf_token == "token-xyz"

    def test_login_missing_csrf_token_is_none(self):
        """Missing X-CSRF-Token header stores None (API may not require it)."""
        client = _make_client()
        login_resp = _mock_response(200, headers={})
        with patch.object(client._session, "post", return_value=login_resp):
            client.login()

        assert client._csrf_token is None

    def test_login_401_raises_auth_error(self):
        """HTTP 401 from login endpoint raises UnifiAuthError."""
        client = _make_client()
        login_resp = _mock_response(401)
        with patch.object(client._session, "post", return_value=login_resp):
            with pytest.raises(UnifiAuthError):
                client.login()

    def test_login_403_raises_auth_error(self):
        """HTTP 403 from login endpoint raises UnifiAuthError."""
        client = _make_client()
        login_resp = _mock_response(403)
        with patch.object(client._session, "post", return_value=login_resp):
            with pytest.raises(UnifiAuthError):
                client.login()

    def test_login_500_raises_api_error(self):
        """HTTP 500 from login endpoint raises UnifiAPIError."""
        client = _make_client()
        login_resp = _mock_response(500)
        with patch.object(client._session, "post", return_value=login_resp):
            with pytest.raises(UnifiAPIError):
                client.login()

    def test_login_network_error_raises_api_error(self):
        """Network-level exception during login raises UnifiAPIError."""
        client = _make_client()
        with patch.object(
            client._session,
            "post",
            side_effect=requests.ConnectionError("timeout"),
        ):
            with pytest.raises(UnifiAPIError, match="Login request failed"):
                client.login()


# ---------------------------------------------------------------------------
# request()
# ---------------------------------------------------------------------------


class TestRequest:
    """Tests for UnifiClient.request()."""

    def _authed_client(self) -> UnifiClient:
        """Return a pre-authenticated client (login already called)."""
        client = _make_client()
        login_resp = _mock_response(
            200, headers={"X-CSRF-Token": "csrf-test"}
        )
        with patch.object(client._session, "post", return_value=login_resp):
            client.login()
        return client

    def test_lazy_login_before_first_request(self):
        """Client logs in automatically before the first request."""
        client = _make_client()
        login_resp = _mock_response(200, headers={"X-CSRF-Token": "t1"})
        api_resp = _mock_response(200, json_data={"data": []})

        with patch.object(
            client._session, "post", return_value=login_resp
        ) as mock_post, patch.object(
            client._session, "request", return_value=api_resp
        ):
            client.request("GET", "/some/path")
            mock_post.assert_called_once()

    def test_csrf_token_sent_in_header(self):
        """X-CSRF-Token header is included in every request after login."""
        client = self._authed_client()
        api_resp = _mock_response(200, json_data={"data": []})

        with patch.object(
            client._session, "request", return_value=api_resp
        ) as mock_req:
            client.request("GET", "/some/path")
            call_kwargs = mock_req.call_args[1]
            assert call_kwargs["headers"]["X-CSRF-Token"] == "csrf-test"

    def test_401_triggers_reauth_and_retry(self):
        """A 401 response causes one re-login and one retry of the request."""
        client = self._authed_client()

        unauth_resp = _mock_response(401)
        unauth_resp.raise_for_status.return_value = None  # don't raise here

        ok_resp = _mock_response(200, json_data={"data": []})
        relogin_resp = _mock_response(200, headers={"X-CSRF-Token": "csrf-new"})

        request_calls = iter([unauth_resp, ok_resp])
        with patch.object(
            client._session, "request", side_effect=request_calls
        ), patch.object(
            client._session, "post", return_value=relogin_resp
        ) as mock_relogin:
            result = client.request("GET", "/some/path")
            mock_relogin.assert_called_once()
            assert result.status_code == 200

    def test_network_error_raises_api_error(self):
        """Raise UnifiAPIError on RequestException during an API call."""
        client = self._authed_client()
        with patch.object(
            client._session,
            "request",
            side_effect=requests.ConnectionError("no route"),
        ):
            with pytest.raises(UnifiAPIError, match="Network error"):
                client.request("GET", "/some/path")

    def test_http_500_raises_api_error(self):
        """HTTP 5xx from an API call raises UnifiAPIError."""
        client = self._authed_client()
        bad_resp = _mock_response(500)

        with patch.object(
            client._session, "request", return_value=bad_resp
        ):
            with pytest.raises(UnifiAPIError):
                client.request("GET", "/some/path")

    def test_is_authenticated_false_before_login(self):
        """is_authenticated() returns False before login is called."""
        client = _make_client()
        assert not client.is_authenticated()

    def test_is_authenticated_true_after_login(self):
        """is_authenticated() returns True after a successful login."""
        client = self._authed_client()
        assert client.is_authenticated()
