"""Unifi firewall group management.

Provides add, remove, and query operations against a named Unifi
``IPv4 Address Group`` (firewall group) via the UDM Pro REST API.

Firewall group endpoint:
  GET /proxy/network/api/s/{site}/rest/firewallgroup
  PUT /proxy/network/api/s/{site}/rest/firewallgroup/{id}
"""

from typing import Optional

from unifi_modules.client import UnifiAPIError, UnifiClient
from utils.logger import get_logger

logger = get_logger(__name__)


class UnifiGroupNotFoundError(UnifiAPIError):
    """Raised when the named firewall group does not exist."""


class UnifiFirewallManager:
    """Manages a single Unifi firewall IP address group.

    All methods are synchronous and safe to call from Flask route
    handlers.  Errors are raised as :class:`UnifiAPIError` sub-classes;
    callers should catch these and log rather than propagate to the user.

    Args:
        client: An authenticated :class:`~unifi_modules.client.UnifiClient`.
        group_name: The exact name of the Unifi firewall group to manage
            (e.g. ``"GameServerAccess"``).
    """

    def __init__(self, client: UnifiClient, group_name: str) -> None:
        """Initialise with an existing client and target group name."""
        self._client = client
        self.group_name = group_name

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def get_firewall_group(self) -> dict:
        """Fetch the firewall group object by name.

        Returns:
            dict: The full group object from the Unifi API, including
                ``_id`` and ``group_members``.

        Raises:
            UnifiGroupNotFoundError: If no group with ``group_name``
                exists in the target site.
            UnifiAPIError: On any API or network error.
        """
        resp = self._client.request("GET", self._group_url())
        groups = resp.json().get("data", [])

        for group in groups:
            if group.get("name") == self.group_name:
                logger.debug(
                    f"Found firewall group '{self.group_name}' "
                    f"(id={group.get('_id')}, "
                    f"members={len(group.get('group_members', []))})"
                )
                return group

        raise UnifiGroupNotFoundError(
            f"Firewall group '{self.group_name}' not found in site "
            f"'{self._client.site}'. "
            "Create it in Network → Firewall & Security → Groups first."
        )

    def get_group_ips(self) -> list:
        """Return the current list of IP addresses in the firewall group.

        Returns:
            list[str]: IP address strings currently in the group.

        Raises:
            UnifiGroupNotFoundError: If the group does not exist.
            UnifiAPIError: On any API or network error.
        """
        group = self.get_firewall_group()
        return list(group.get("group_members", []))

    def add_ip(self, ip: str) -> bool:
        """Add an IP address to the firewall group.

        If the IP is already present the group is left unchanged and
        ``False`` is returned (idempotent — not an error).

        Args:
            ip: IPv4 address string to add (e.g. ``"1.2.3.4"``).

        Returns:
            bool: ``True`` if the group was updated, ``False`` if the IP
                was already present.

        Raises:
            UnifiGroupNotFoundError: If the group does not exist.
            UnifiAPIError: On any API or network error.
        """
        group = self.get_firewall_group()
        members: list = list(group.get("group_members", []))

        if ip in members:
            logger.info(
                f"IP {ip} already in Unifi group '{self.group_name}' — "
                "no update needed"
            )
            return False

        members.append(ip)
        self._put_group(group, members)
        logger.info(f"✅ Added {ip} to Unifi firewall group '{self.group_name}'")
        return True

    def remove_ip(self, ip: str) -> bool:
        """Remove an IP address from the firewall group.

        If the IP is not present the group is left unchanged and
        ``False`` is returned (idempotent — not an error).

        Args:
            ip: IPv4 address string to remove.

        Returns:
            bool: ``True`` if the group was updated, ``False`` if the IP
                was not in the group.

        Raises:
            UnifiGroupNotFoundError: If the group does not exist.
            UnifiAPIError: On any API or network error.
        """
        group = self.get_firewall_group()
        members: list = list(group.get("group_members", []))

        if ip not in members:
            logger.info(
                f"IP {ip} not in Unifi group '{self.group_name}' — " "no update needed"
            )
            return False

        members.remove(ip)
        self._put_group(group, members)
        logger.info(f"✅ Removed {ip} from Unifi firewall group '{self.group_name}'")
        return True

    def sync_group(self, ip_list: list) -> None:
        """Replace the firewall group members with the given IP list.

        Used by the Phase 5 cleanup scheduler to synchronise the Unifi
        group with the active IPs stored in the database.

        Args:
            ip_list: Complete list of IP address strings that should be
                in the group after this call.

        Raises:
            UnifiGroupNotFoundError: If the group does not exist.
            UnifiAPIError: On any API or network error.
        """
        group = self.get_firewall_group()
        current: list = list(group.get("group_members", []))
        desired: list = list(ip_list)

        if sorted(current) == sorted(desired):
            logger.info(
                f"Unifi group '{self.group_name}' already in sync "
                f"({len(desired)} IPs) — no update needed"
            )
            return

        self._put_group(group, desired)
        logger.info(
            f"✅ Synced Unifi firewall group '{self.group_name}': "
            f"{len(current)} → {len(desired)} IPs"
        )

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _group_url(self, group_id: Optional[str] = None) -> str:
        """Build the firewall group API path.

        Args:
            group_id: If provided, appends ``/{group_id}`` for PUT calls.

        Returns:
            str: URL path (no base URL prefix).
        """
        base = f"/proxy/network/api/s/{self._client.site}/rest/firewallgroup"
        return f"{base}/{group_id}" if group_id else base

    def _put_group(self, group: dict, new_members: list) -> None:
        """PUT the updated group back to the Unifi API.

        Sends only the fields expected by the API (the full group object
        from the GET response, with ``group_members`` replaced).

        Args:
            group: Original group dict from :meth:`get_firewall_group`.
            new_members: Updated list of IP address strings.

        Raises:
            UnifiAPIError: On any API or network error.
        """
        group_id: str = group["_id"]
        payload = dict(group)
        payload["group_members"] = new_members

        self._client.request(
            "PUT",
            self._group_url(group_id),
            json=payload,
        )
