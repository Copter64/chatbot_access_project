"""Background scheduler for periodic IP cleanup tasks.

Uses APScheduler's ``BackgroundScheduler`` to run a cleanup job at a
configurable interval.  The cleanup coroutine is dispatched onto the main
asyncio event loop so it shares the same database connection as the rest
of the application.
"""

import asyncio
from typing import Callable, Optional

from apscheduler.schedulers.background import BackgroundScheduler

from utils.logger import get_logger

logger = get_logger(__name__)

# Module-level scheduler instance so it can be stopped gracefully.
_scheduler: Optional[BackgroundScheduler] = None


async def cleanup_expired_ips(db, unifi_manager) -> dict:
    """Remove expired IP addresses from Unifi and mark them inactive in DB.

    Fetches every ``ip_addresses`` row where ``is_active = 1`` and
    ``expires_at <= now``.  For each such row the IP is removed from the
    Unifi firewall group (best-effort — a Unifi error is logged but does
    **not** prevent the database update).  The row is then marked
    ``is_active = 0`` in the database.

    Args:
        db: Initialised :class:`~database.models.Database` instance.
        unifi_manager: Initialised
            :class:`~unifi_modules.firewall.UnifiFirewallManager` instance,
            or ``None`` if Unifi integration is unavailable.

    Returns:
        dict: Summary with keys ``"removed"`` (int), ``"skipped"`` (int),
            and ``"unifi_errors"`` (int).
    """
    expired = await db.get_expired_active_ips()

    if not expired:
        logger.info("Cleanup: no expired IPs found — nothing to do")
        return {"removed": 0, "skipped": 0, "unifi_errors": 0}

    logger.info(f"Cleanup: found {len(expired)} expired IP(s) to process")

    removed = 0
    skipped = 0
    unifi_errors = 0

    for record in expired:
        ip = record["ip_address"]
        ip_id = record["id"]

        # Step 1: remove from Unifi (best-effort)
        if unifi_manager is not None:
            try:
                unifi_manager.remove_ip(ip)
            except Exception as exc:
                logger.error(
                    f"Cleanup: failed to remove {ip} from Unifi firewall "
                    f"group: {exc}"
                )
                unifi_errors += 1

        # Step 2: deactivate in DB regardless of Unifi outcome
        deactivated = await db.deactivate_ip(ip_id)
        if deactivated:
            removed += 1
            logger.debug(f"Cleanup: deactivated IP id={ip_id} ({ip})")
        else:
            skipped += 1
            logger.warning(f"Cleanup: ip_id={ip_id} ({ip}) not found in DB — skipping")

    logger.info(
        f"Cleanup complete: {removed} removed, "
        f"{skipped} skipped, "
        f"{unifi_errors} Unifi error(s)"
    )
    return {"removed": removed, "skipped": skipped, "unifi_errors": unifi_errors}


async def warn_expiring_ips(
    db,
    warning_callback: Optional[Callable[[str, str, str], None]],
    warning_days: int,
) -> dict:
    """Send expiry warning DMs for IPs expiring within *warning_days* days.

    Queries the database for active IP records that expire within
    ``warning_days`` days and have not yet had a warning sent
    (``warning_sent = 0``).  For each such record the ``warning_callback``
    is called with ``(discord_id, ip_address, expires_date)`` and the row is
    marked so the user is not warned again for the same access period.

    Args:
        db: Initialised :class:`~database.models.Database` instance.
        warning_callback: Sync callable ``(discord_id, ip, expires)`` that
            fires the DM.  When ``None`` the function is a no-op.
        warning_days: Look-ahead window in days.

    Returns:
        dict: Summary with keys ``"warned"`` (int) and ``"errors"`` (int).
    """
    if warning_callback is None:
        return {"warned": 0, "errors": 0}

    expiring = await db.get_ips_expiring_soon(warning_days)

    if not expiring:
        logger.info("Expiry warning: no IPs expiring soon — nothing to do")
        return {"warned": 0, "errors": 0}

    logger.info(
        f"Expiry warning: found {len(expiring)} IP(s) expiring within "
        f"{warning_days} day(s)"
    )

    warned = 0
    errors = 0

    for record in expiring:
        ip_id = record["id"]
        ip = record["ip_address"]
        discord_id = record["discord_id"]
        # expires_at may include a time component — keep only the date part
        expires = str(record["expires_at"])[:10]

        try:
            warning_callback(discord_id, ip, expires)
            await db.mark_ip_warning_sent(ip_id)
            warned += 1
            logger.debug(
                f"Expiry warning queued for discord_id={discord_id}, "
                f"ip={ip}, expires={expires}"
            )
        except Exception as exc:
            logger.error(
                f"Expiry warning failed for ip_id={ip_id} ({ip}): {exc}",
                exc_info=True,
            )
            errors += 1

    logger.info(
        f"Expiry warning complete: {warned} warned, {errors} error(s)"
    )
    return {"warned": warned, "errors": errors}


def start_scheduler(
    db,
    loop: asyncio.AbstractEventLoop,
    unifi_manager=None,
    interval_hours: int = 24,
    interval_seconds: int = 0,
    warning_callback: Optional[Callable[[str, str, str], None]] = None,
    warning_days: int = 3,
) -> BackgroundScheduler:
    """Start the background cleanup scheduler.

    Creates a :class:`~apscheduler.schedulers.background.BackgroundScheduler`
    with a single interval job that calls :func:`cleanup_expired_ips` and
    :func:`warn_expiring_ips` every ``interval_hours`` hours (or
    ``interval_seconds`` seconds when that is non-zero).  Coroutines are
    dispatched onto ``loop`` via :func:`asyncio.run_coroutine_threadsafe` so
    they run safely alongside the Discord bot and web server.

    Args:
        db: Initialised :class:`~database.models.Database` instance.
        loop: The running asyncio event loop (from ``asyncio.get_running_loop()``
            inside the ``main`` coroutine).
        unifi_manager: Optional Unifi firewall manager.
        interval_hours: How often to run the job in hours.  Defaults to 24.
            Ignored when ``interval_seconds`` is non-zero.
        interval_seconds: Override interval in seconds.  Non-zero values take
            precedence over ``interval_hours``.  Intended for testing only.
        warning_callback: Optional sync callable ``(discord_id, ip, expires)``
            used to send expiry warning DMs.  When ``None`` warnings are skipped.
        warning_days: How many days before expiry to send the DM.  Defaults to 3.

    Returns:
        BackgroundScheduler: The started scheduler (also stored in the
            module-level ``_scheduler`` variable).
    """
    global _scheduler

    def _job() -> None:
        """Sync wrapper that schedules cleanup and warning coroutines."""
        # Run expiry cleanup
        future = asyncio.run_coroutine_threadsafe(
            cleanup_expired_ips(db, unifi_manager), loop
        )
        try:
            future.result(timeout=300)
        except asyncio.TimeoutError:
            logger.error("Cleanup job timed out after 300 s")
        except Exception as exc:
            logger.error(
                f"Cleanup job raised an unexpected error: {exc}", exc_info=True
            )

        # Run expiry warnings
        warn_future = asyncio.run_coroutine_threadsafe(
            warn_expiring_ips(db, warning_callback, warning_days), loop
        )
        try:
            warn_future.result(timeout=60)
        except asyncio.TimeoutError:
            logger.error("Expiry warning job timed out after 60 s")
        except Exception as exc:
            logger.error(
                f"Expiry warning job raised an unexpected error: {exc}",
                exc_info=True,
            )

    _scheduler = BackgroundScheduler(daemon=True)

    # interval_seconds (non-zero) takes precedence — intended for testing.
    if interval_seconds > 0:
        trigger_kwargs = {"seconds": interval_seconds}
        interval_desc = f"{interval_seconds}s"
    else:
        trigger_kwargs = {"hours": interval_hours}
        interval_desc = f"{interval_hours}h"

    _scheduler.add_job(
        _job,
        trigger="interval",
        **trigger_kwargs,
        id="cleanup_expired_ips",
        name="IP expiry cleanup",
        misfire_grace_time=3600,  # allow up to 1 h late start
    )
    _scheduler.start()
    logger.info(f"✅ Cleanup scheduler started — runs every {interval_desc}")
    return _scheduler


def stop_scheduler() -> None:
    """Gracefully shut down the background scheduler, if running."""
    global _scheduler
    if _scheduler is not None and _scheduler.running:
        _scheduler.shutdown(wait=False)
        logger.info("Cleanup scheduler stopped")
    _scheduler = None
