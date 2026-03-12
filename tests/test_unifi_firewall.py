"""Tests for unifi_modules.firewall.UnifiFirewallManager."""

from unittest.mock import MagicMock

import pytest

from unifi_modules.client import UnifiAPIError, UnifiClient
from unifi_modules.firewall import UnifiFirewallManager, UnifiGroupNotFoundError

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_GROUP_ID = "abc123def456"
_GROUP_NAME = "GameServerAccess"


def _make_manager(group_members=None) -> tuple:
    """Return (manager, mock_client) with a pre-configured group."""
    members = group_members if group_members is not None else ["1.1.1.1"]
    group_data = {
        "_id": _GROUP_ID,
        "name": _GROUP_NAME,
        "group_type": "address-group",
        "group_members": members,
    }

    mock_client = MagicMock(spec=UnifiClient)
    mock_client.site = "default"
    mock_client.request.return_value = MagicMock(
        json=MagicMock(return_value={"data": [group_data]})
    )

    manager = UnifiFirewallManager(mock_client, _GROUP_NAME)
    return manager, mock_client, group_data


def _make_empty_manager() -> tuple:
    """Return (manager, mock_client) where the group has no members."""
    return _make_manager(group_members=[])


# ---------------------------------------------------------------------------
# get_firewall_group()
# ---------------------------------------------------------------------------


class TestGetFirewallGroup:
    """Tests for UnifiFirewallManager.get_firewall_group()."""

    def test_returns_matching_group(self):
        """Returns group dict when name matches."""
        manager, _, group_data = _make_manager()
        result = manager.get_firewall_group()
        assert result["name"] == _GROUP_NAME
        assert result["_id"] == _GROUP_ID

    def test_raises_when_group_not_found(self):
        """Raises UnifiGroupNotFoundError when group name is absent."""
        mock_client = MagicMock(spec=UnifiClient)
        mock_client.site = "default"
        mock_client.request.return_value = MagicMock(
            json=MagicMock(return_value={"data": []})
        )
        manager = UnifiFirewallManager(mock_client, "NonExistentGroup")

        with pytest.raises(UnifiGroupNotFoundError, match="NonExistentGroup"):
            manager.get_firewall_group()

    def test_api_error_propagates(self):
        """Propagate UnifiAPIError from the client unchanged."""
        mock_client = MagicMock(spec=UnifiClient)
        mock_client.site = "default"
        mock_client.request.side_effect = UnifiAPIError("connection refused")
        manager = UnifiFirewallManager(mock_client, _GROUP_NAME)

        with pytest.raises(UnifiAPIError, match="connection refused"):
            manager.get_firewall_group()


# ---------------------------------------------------------------------------
# get_group_ips()
# ---------------------------------------------------------------------------


class TestGetGroupIps:
    """Tests for UnifiFirewallManager.get_group_ips()."""

    def test_returns_current_member_list(self):
        """Returns the list of IPs in the group."""
        manager, _, _ = _make_manager(group_members=["1.2.3.4", "5.6.7.8"])
        assert manager.get_group_ips() == ["1.2.3.4", "5.6.7.8"]

    def test_returns_empty_list_for_empty_group(self):
        """Returns empty list when group has no members."""
        manager, _, _ = _make_empty_manager()
        assert manager.get_group_ips() == []


# ---------------------------------------------------------------------------
# add_ip()
# ---------------------------------------------------------------------------


class TestAddIp:
    """Tests for UnifiFirewallManager.add_ip()."""

    def test_adds_new_ip_returns_true(self):
        """Returns True and PUTs updated group when IP is new."""
        manager, mock_client, _ = _make_manager(group_members=["1.1.1.1"])
        # Second call (after add) — not needed but set up anyway
        result = manager.add_ip("2.2.2.2")

        assert result is True
        # Should have called request twice: GET + PUT
        assert mock_client.request.call_count == 2

    def test_put_includes_new_ip(self):
        """PUT payload contains the new IP appended to existing members."""
        manager, mock_client, _ = _make_manager(group_members=["1.1.1.1"])
        manager.add_ip("9.9.9.9")

        put_call = mock_client.request.call_args_list[1]
        payload = put_call[1]["json"]
        assert "9.9.9.9" in payload["group_members"]
        assert "1.1.1.1" in payload["group_members"]

    def test_duplicate_ip_returns_false(self):
        """Returns False and does NOT PUT when IP is already present."""
        manager, mock_client, _ = _make_manager(group_members=["1.1.1.1"])
        result = manager.add_ip("1.1.1.1")

        assert result is False
        # Only the GET; no PUT
        assert mock_client.request.call_count == 1

    def test_add_to_empty_group(self):
        """Can add an IP to a group that has no existing members."""
        manager, mock_client, _ = _make_empty_manager()
        result = manager.add_ip("3.3.3.3")

        assert result is True
        put_call = mock_client.request.call_args_list[1]
        payload = put_call[1]["json"]
        assert payload["group_members"] == ["3.3.3.3"]


# ---------------------------------------------------------------------------
# remove_ip()
# ---------------------------------------------------------------------------


class TestRemoveIp:
    """Tests for UnifiFirewallManager.remove_ip()."""

    def test_removes_existing_ip_returns_true(self):
        """Returns True and PUTs updated group when IP is present."""
        manager, mock_client, _ = _make_manager(group_members=["1.1.1.1", "2.2.2.2"])
        result = manager.remove_ip("1.1.1.1")

        assert result is True
        assert mock_client.request.call_count == 2

    def test_put_excludes_removed_ip(self):
        """PUT payload does not contain the removed IP."""
        manager, mock_client, _ = _make_manager(group_members=["1.1.1.1", "2.2.2.2"])
        manager.remove_ip("1.1.1.1")

        put_call = mock_client.request.call_args_list[1]
        payload = put_call[1]["json"]
        assert "1.1.1.1" not in payload["group_members"]
        assert "2.2.2.2" in payload["group_members"]

    def test_absent_ip_returns_false(self):
        """Returns False and does NOT PUT when IP is not in the group."""
        manager, mock_client, _ = _make_manager(group_members=["1.1.1.1"])
        result = manager.remove_ip("9.9.9.9")

        assert result is False
        assert mock_client.request.call_count == 1

    def test_remove_last_ip_leaves_empty_group(self):
        """Removing the only member results in an empty group_members list."""
        manager, mock_client, _ = _make_manager(group_members=["1.1.1.1"])
        manager.remove_ip("1.1.1.1")

        put_call = mock_client.request.call_args_list[1]
        payload = put_call[1]["json"]
        assert payload["group_members"] == []


# ---------------------------------------------------------------------------
# sync_group()
# ---------------------------------------------------------------------------


class TestSyncGroup:
    """Tests for UnifiFirewallManager.sync_group()."""

    def test_sync_puts_new_list(self):
        """PUT is called with the desired IP list."""
        manager, mock_client, _ = _make_manager(group_members=["1.1.1.1"])
        manager.sync_group(["2.2.2.2", "3.3.3.3"])

        assert mock_client.request.call_count == 2
        put_call = mock_client.request.call_args_list[1]
        assert sorted(put_call[1]["json"]["group_members"]) == [
            "2.2.2.2",
            "3.3.3.3",
        ]

    def test_sync_no_op_when_already_in_sync(self):
        """No PUT is issued when the group already matches the desired list."""
        manager, mock_client, _ = _make_manager(group_members=["1.1.1.1", "2.2.2.2"])
        # Same IPs — order shouldn't matter
        manager.sync_group(["2.2.2.2", "1.1.1.1"])

        # Only the GET call
        assert mock_client.request.call_count == 1

    def test_sync_to_empty_list(self):
        """Syncing to empty list clears all group members."""
        manager, mock_client, _ = _make_manager(group_members=["1.1.1.1"])
        manager.sync_group([])

        put_call = mock_client.request.call_args_list[1]
        assert put_call[1]["json"]["group_members"] == []
