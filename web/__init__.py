"""Web server module for Discord Game Server Access Bot.

Provides a Flask web server that captures user external IPs
via token-validated links sent through Discord DMs.
"""

from web.app import create_app, run_web_server

__all__ = ["create_app", "run_web_server"]
