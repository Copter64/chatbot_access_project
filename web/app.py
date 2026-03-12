"""Flask web application factory and server runner.

This module creates and configures the Flask app and provides
a function to run it in a background thread alongside the Discord bot.
"""

import asyncio
import ssl
import threading
from typing import TYPE_CHECKING, Any, Callable, Optional

from flask import Flask, Response

from config import Config
from utils.logger import get_logger
from web.security import SecurityManager

if TYPE_CHECKING:
    from unifi_modules.firewall import UnifiFirewallManager

logger = get_logger(__name__)


def create_app(
    db: Any,
    loop: asyncio.AbstractEventLoop,
    alert_callback: Optional[Callable[[str, str], None]] = None,
    unifi_manager: Optional["UnifiFirewallManager"] = None,
    server_info_callback: Optional[Callable[[str, str, str], None]] = None,
) -> Flask:
    """Create and configure the Flask application.

    Args:
        db: Initialized Database instance.
        loop: The running asyncio event loop from the bot process.
        alert_callback: Optional callable(ip, detail) invoked by the
            SecurityManager when a brute-force threshold is reached.
        unifi_manager: Optional :class:`~unifi_modules.firewall.UnifiFirewallManager`
            instance.  When provided, confirmed IPs are pushed to the
            Unifi firewall group immediately after DB insertion.
        server_info_callback: Optional callable(discord_user_id, ip, expires)
            invoked after a user's IP is successfully confirmed.  Used to
            send the game-server connection details DM from the bot.

    Returns:
        Flask: Configured Flask application instance.
    """
    app = Flask(__name__, template_folder="templates")
    app.secret_key = Config.SECRET_KEY or "dev-insecure-key"
    # Limit request bodies to 16 KB — no legitimate use case needs more
    app.config["MAX_CONTENT_LENGTH"] = 16 * 1024

    # Build the per-IP security manager
    security = SecurityManager(
        rate_limit_requests=Config.WEB_RATE_LIMIT_REQUESTS,
        rate_limit_window_seconds=Config.WEB_RATE_LIMIT_WINDOW_SECONDS,
        brute_force_threshold=Config.WEB_BRUTE_FORCE_THRESHOLD,
        alert_callback=alert_callback,
    )

    # Inject shared resources into app config for use in routes
    app.config["DB"] = db
    app.config["LOOP"] = loop
    app.config["IP_EXPIRATION_DAYS"] = Config.IP_EXPIRATION_DAYS
    app.config["SECURITY"] = security
    app.config["UNIFI"] = unifi_manager  # None until Phase 4 wired
    app.config["SERVER_INFO_CALLBACK"] = server_info_callback

    # Register routes blueprint
    from web.routes import bp  # noqa: E402 (avoid circular import at module top)

    app.register_blueprint(bp)

    @app.after_request
    def add_security_headers(response: Response) -> Response:
        """Attach security headers to every response."""
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; style-src 'self' 'unsafe-inline'"
        )
        return response

    logger.info("Flask application created and routes registered")
    return app


def run_web_server(app: Flask) -> threading.Thread:
    """Start the Flask web server in a daemon thread.

    If SSL_CERT and SSL_KEY are configured, the server runs over HTTPS.
    Otherwise it falls back to plain HTTP (useful for local development).

    Args:
        app: Configured Flask application instance.

    Returns:
        threading.Thread: The background thread running the server.
    """
    ssl_context = None
    if Config.SSL_CERT and Config.SSL_KEY:
        ssl_context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        ssl_context.load_cert_chain(certfile=Config.SSL_CERT, keyfile=Config.SSL_KEY)
        logger.info(f"TLS enabled — cert: {Config.SSL_CERT}")
    else:
        logger.warning("SSL_CERT/SSL_KEY not set — web server running over plain HTTP")

    def _run() -> None:
        """Run Flask server (executed in daemon thread)."""
        scheme = "https" if ssl_context else "http"
        logger.info(
            f"Web server starting on " f"{scheme}://{Config.WEB_HOST}:{Config.WEB_PORT}"
        )
        app.run(
            host=Config.WEB_HOST,
            port=Config.WEB_PORT,
            debug=False,
            use_reloader=False,
            ssl_context=ssl_context,
        )

    thread = threading.Thread(target=_run, daemon=True, name="web-server")
    thread.start()
    logger.info("Web server thread started")
    return thread
