"""Unifi integration package.

Provides UDM Pro API authentication and firewall group management.
"""

from unifi_modules.client import UnifiAPIError, UnifiAuthError, UnifiClient
from unifi_modules.firewall import UnifiFirewallManager, UnifiGroupNotFoundError

__all__ = [
    "UnifiClient",
    "UnifiAPIError",
    "UnifiAuthError",
    "UnifiFirewallManager",
    "UnifiGroupNotFoundError",
]
