"""Flask route handlers for the IP capture web flow.

Endpoints:
    GET  /check-ip/<token>    - Validates token, shows user their IP, confirm btn
    POST /confirm-ip/<token>  - Saves IP to database and marks token used
    GET  /health              - Health check endpoint
"""

import asyncio
import ipaddress
import re
from datetime import datetime, timedelta, timezone
from typing import Any

from flask import Blueprint, current_app, redirect, render_template, request, url_for

from utils.logger import get_logger
from utils.token_generator import is_valid_token_format

logger = get_logger(__name__)

bp = Blueprint("main", __name__)


def _run_async(coro: Any) -> Any:
    """Run an async coroutine from a synchronous Flask route.

    Uses the shared asyncio event loop injected into the Flask app config
    to safely bridge synchronous Flask handlers and async database calls.

    Args:
        coro: Awaitable coroutine to execute.

    Returns:
        The result of the coroutine.

    Raises:
        Exception: Propagates any exception raised by the coroutine.
    """
    loop: asyncio.AbstractEventLoop = current_app.config["LOOP"]
    future = asyncio.run_coroutine_threadsafe(coro, loop)
    return future.result(timeout=10)


def _get_client_ip() -> str:
    """Return the real client IP address.

    Uses ``request.remote_addr`` directly, which is the actual TCP peer
    address. We intentionally ignore ``X-Forwarded-For`` because this
    server is not behind a trusted reverse proxy — any client can forge
    that header, which would defeat IP-based rate limiting.

    Returns:
        str: The client's IP address string.
    """
    return request.remote_addr or "unknown"


def _is_public_ip(ip_str: str) -> bool:
    """Return True if *ip_str* is a publicly routable IP address.

    Rejects RFC 1918 private addresses (10.x, 172.16-31.x, 192.168.x),
    loopback (127.x / ::1), link-local (169.254.x), and all other
    non-globally-routable ranges.

    Args:
        ip_str: IP address string to check.

    Returns:
        bool: True if the address is globally routable, False otherwise.
    """
    try:
        return ipaddress.ip_address(ip_str).is_global
    except ValueError:
        return False


def _security():
    """Return the SecurityManager from the current app config."""
    return current_app.config["SECURITY"]


@bp.route("/robots.txt")
def robots():
    """Instruct crawlers not to index any routes on this server."""
    return (
        "User-agent: *\nDisallow: /\n",
        200,
        {"Content-Type": "text/plain"},
    )


@bp.route("/favicon.ico")
def favicon():
    """Return empty favicon to prevent 404 log noise in browsers."""
    return "", 204


@bp.route("/health")
def health() -> tuple:
    """Health check endpoint.

    Returns:
        tuple: JSON response and HTTP 200 status code.
    """
    return {"status": "ok"}, 200


@bp.route("/check-ip/<token>", methods=["GET"])
def check_ip(token: str):
    """Display the user's external IP and ask them to confirm.

    Validates the token and renders a confirmation page showing the
    detected IP address. Token must be valid, unexpired, and unused.

    Args:
        token: The unique access token from the Discord DM link.

    Returns:
        Rendered HTML template (check_ip or error).
    """
    client_ip = _get_client_ip()
    logger.info(f"GET /check-ip/{token[:8]}... from {client_ip}")

    # Reject RFC 1918 / non-routable IPs — only public addresses are useful
    if not _is_public_ip(client_ip):
        logger.warning(f"Non-public IP rejected on check-ip: {client_ip!r}")
        return (
            render_template(
                "error.html",
                error_title="Private IP Address Detected",
                error_message=(
                    "Your detected IP address is from a private or "
                    "non-routable network. Please connect from a publicly "
                    "routable IP address and try again."
                ),
            ),
            400,
        )

    # Per-IP rate limit check
    if _security().is_rate_limited(client_ip):
        return (
            render_template(
                "error.html",
                error_title="Too Many Requests",
                error_message=(
                    "You are making too many requests. "
                    "Please wait a moment and try again."
                ),
            ),
            429,
        )

    # Validate token format before hitting the DB
    if not is_valid_token_format(token):
        logger.warning(f"Invalid token format received: {token[:16]}")
        _security().record_error(client_ip)
        return (
            render_template(
                "error.html",
                error_title="Invalid Link",
                error_message=(
                    "This link is invalid. Please request a new access link "
                    "from the Discord bot using /request-access."
                ),
            ),
            400,
        )

    # Validate token exists, is unused, and is not expired
    try:
        token_data = _run_async(current_app.config["DB"].get_token(token))
    except Exception as e:
        logger.error(f"Database error during token lookup: {e}", exc_info=True)
        return (
            render_template(
                "error.html",
                error_title="Server Error",
                error_message="A server error occurred. Please try again later.",
            ),
            500,
        )

    if token_data is None:
        logger.info(f"Token not found or expired: {token[:8]}...")
        _security().record_error(client_ip)
        return (
            render_template(
                "error.html",
                error_title="Link Expired or Already Used",
                error_message=(
                    "This link has expired or has already been used. "
                    "Please request a new access link from the Discord bot "
                    "using /request-access."
                ),
            ),
            410,
        )

    expiration_days = current_app.config["IP_EXPIRATION_DAYS"]

    logger.info(
        f"Showing IP confirmation to user_id={token_data['user_id']}, "
        f"ip={client_ip}"
    )

    return render_template(
        "check_ip.html",
        ip_address=client_ip,
        expiration_days=expiration_days,
        token=token,
    )


@bp.route("/confirm-ip/<token>", methods=["POST"])
def confirm_ip(token: str):
    """Save the user's IP and mark the token as used.

    Re-validates the token on POST, records the IP in the database,
    marks the token as used, then redirects to the success page.

    Args:
        token: The unique access token from the form submission.

    Returns:
        Redirect to success page, or rendered error page.
    """
    client_ip = _get_client_ip()
    logger.info(f"POST /confirm-ip/{token[:8]}... from {client_ip}")

    # Reject RFC 1918 / non-routable IPs — only public addresses are useful
    if not _is_public_ip(client_ip):
        logger.warning(f"Non-public IP rejected on confirm-ip: {client_ip!r}")
        return (
            render_template(
                "error.html",
                error_title="Private IP Address Detected",
                error_message=(
                    "Your detected IP address is from a private or "
                    "non-routable network. Please connect from a publicly "
                    "routable IP address and try again."
                ),
            ),
            400,
        )

    # Per-IP rate limit check
    if _security().is_rate_limited(client_ip):
        return (
            render_template(
                "error.html",
                error_title="Too Many Requests",
                error_message=(
                    "You are making too many requests. "
                    "Please wait a moment and try again."
                ),
            ),
            429,
        )

    # Re-validate token format
    if not is_valid_token_format(token):
        logger.warning(f"Invalid token format on confirm: {token[:16]}")
        _security().record_error(client_ip)
        return (
            render_template(
                "error.html",
                error_title="Invalid Link",
                error_message=(
                    "This link is invalid. Please request a new access link "
                    "from the Discord bot using /request-access."
                ),
            ),
            400,
        )

    db = current_app.config["DB"]

    # Re-fetch token to prevent double-use race conditions
    try:
        token_data = _run_async(db.get_token(token))
    except Exception as e:
        logger.error(f"Database error on confirm lookup: {e}", exc_info=True)
        return (
            render_template(
                "error.html",
                error_title="Server Error",
                error_message="A server error occurred. Please try again later.",
            ),
            500,
        )

    if token_data is None:
        logger.warning(f"Token already used or expired on confirm: {token[:8]}...")
        _security().record_error(client_ip)
        return (
            render_template(
                "error.html",
                error_title="Link Expired or Already Used",
                error_message=(
                    "This link has expired or has already been used. "
                    "Please request a new access link from the Discord bot "
                    "using /request-access."
                ),
            ),
            410,
        )

    user_id = token_data["user_id"]
    expiration_days = current_app.config["IP_EXPIRATION_DAYS"]
    expires_at = datetime.now(timezone.utc) + timedelta(days=expiration_days)

    try:
        # Mark token as used (atomic — prevents double submission)
        marked = _run_async(db.mark_token_used(token, client_ip))
        if not marked:
            # Token was used between our check and this update
            logger.warning(f"Token race condition on confirm: {token[:8]}...")
            return (
                render_template(
                    "error.html",
                    error_title="Link Already Used",
                    error_message=(
                        "This link has already been used. "
                        "Please request a new access link using /request-access."
                    ),
                ),
                410,
            )

        # Add IP address to the database
        _run_async(db.add_ip_address(user_id, client_ip, expires_at.isoformat()))

        # Audit log
        _run_async(
            db.log_request(
                user_id,
                "ip_confirmed",
                success=True,
                ip_address=client_ip,
            )
        )

        logger.info(
            f"IP {client_ip} confirmed and saved for user_id={user_id}, "
            f"expires={expires_at.date()}"
        )

        # Push IP to Unifi firewall group (best-effort — DB is authoritative).
        # A Unifi failure never blocks the user from seeing the success page.
        unifi = current_app.config.get("UNIFI")
        if unifi is not None:
            try:
                added = unifi.add_ip(client_ip)
                if added:
                    logger.info(f"✅ IP {client_ip} added to Unifi firewall group")
                else:
                    logger.info(
                        f"IP {client_ip} already present in Unifi firewall group"
                    )
            except Exception as unifi_exc:
                logger.error(
                    f"Unifi API error adding {client_ip} — "
                    f"DB record saved, manual sync may be needed: {unifi_exc}",
                    exc_info=True,
                )

        # Send server connection info DM to the user (best-effort).
        # Failure here never blocks the success response.
        server_info_cb = current_app.config.get("SERVER_INFO_CALLBACK")
        if server_info_cb is not None:
            try:
                user_row = _run_async(db.get_user_by_id(user_id))
                if user_row:
                    server_info_cb(
                        user_row["discord_id"],
                        client_ip,
                        expires_at.strftime("%Y-%m-%d"),
                    )
            except Exception as cb_exc:
                logger.error(
                    f"Server info DM callback failed for user_id={user_id}: {cb_exc}",
                    exc_info=True,
                )

    except Exception as e:
        logger.error(f"Database error saving IP: {e}", exc_info=True)
        return (
            render_template(
                "error.html",
                error_title="Server Error",
                error_message="A server error occurred while saving your IP. "
                "Please try again later.",
            ),
            500,
        )

    return redirect(
        url_for(
            "main.success",
            ip=client_ip,
            expires=expires_at.strftime("%Y-%m-%d"),
        )
    )


@bp.route("/success")
def success():
    """Display the IP access confirmation success page.

    Reads IP and expiry date from URL query parameters set by confirm_ip.
    Both parameters are validated before rendering to ensure no garbage
    or injection attempt reaches the template or the user.

    Returns:
        Rendered success HTML template, or redirect to error on bad params.
    """
    ip_param = request.args.get("ip", "")
    expires_param = request.args.get("expires", "")

    # Validate IP address
    try:
        ipaddress.ip_address(ip_param)
    except ValueError:
        logger.warning(f"Invalid IP on success page: {ip_param!r}")
        return (
            render_template(
                "error.html",
                error_title="Invalid Request",
                error_message="This page was reached with invalid parameters.",
            ),
            400,
        )

    # Validate date format (YYYY-MM-DD)
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", expires_param):
        logger.warning(f"Invalid expires on success page: {expires_param!r}")
        return (
            render_template(
                "error.html",
                error_title="Invalid Request",
                error_message="This page was reached with invalid parameters.",
            ),
            400,
        )

    logger.info(f"Success page viewed for ip={ip_param}, expires={expires_param}")

    return render_template(
        "success.html",
        ip_address=ip_param,
        expires=expires_param,
    )
