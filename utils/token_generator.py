"""Token generation utilities.

Provides secure random token generation for access links.
"""

import secrets
import string
from typing import Optional


def generate_token(length: int = 32) -> str:
    """Generate a cryptographically secure random token.

    Args:
        length: Length of the token. Default is 32 characters.

    Returns:
        str: A secure random token string.
    """
    # Use URL-safe characters (letters, digits, and some special chars)
    alphabet = string.ascii_letters + string.digits + "-_"
    token = "".join(secrets.choice(alphabet) for _ in range(length))
    return token


def generate_access_token() -> str:
    """Generate an access token for IP verification.

    Returns:
        str: A 32-character secure random token.
    """
    return generate_token(32)


def is_valid_token_format(token: Optional[str]) -> bool:
    """Check if a token has a valid format.

    Args:
        token: Token string to validate.

    Returns:
        bool: True if token format is valid, False otherwise.
    """
    if not token:
        return False

    # Check length
    if len(token) < 16 or len(token) > 128:
        return False

    # Check characters (alphanumeric, hyphen, underscore)
    allowed = set(string.ascii_letters + string.digits + "-_")
    return all(c in allowed for c in token)
