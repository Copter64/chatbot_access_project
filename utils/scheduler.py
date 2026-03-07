"""Background scheduler for periodic IP cleanup tasks.

Uses APScheduler's ``BackgroundScheduler`` to run a cleanup job at a
configurable interval.  The cleanup coroutine is dispatched onto the main
asyncio event loop so it shares the same database connection as the rest
of the application.
"""

import asyncio
from typing import Optional

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


def start_scheduler(
    db,
    loop: asyncio.AbstractEventLoop,
    unifi_manager=None,
    interval_hours: int = 24,
) -> BackgroundScheduler:
    """Start the background cleanup scheduler.

    Creates a :class:`~apscheduler.schedulers.background.BackgroundScheduler`
    with a single interval job that calls :func:`cleanup_expired_ips` every
    ``interval_hours`` hours.  The coroutine is dispatched onto ``loop`` via
    :func:`asyncio.run_coroutine_threadsafe` so it runs safely alongside the
    Discord bot and web server.

    Args:
        db: Initialised :class:`~database.models.Database` instance.
        loop: The running asyncio event loop (from ``asyncio.get_running_loop()``
            inside the ``main`` coroutine).
        unifi_manager: Optional Unifi firewall manager.
        interval_hours: How often to run the cleanup job.  Defaults to 24.

    Returns:
        BackgroundScheduler: The started scheduler (also stored in the
            module-level ``_scheduler`` variable).
    """
    global _scheduler

    def _job() -> None:
        """Sync wrapper that schedules the cleanup coroutine on the event loop."""
        future = asyncio.run_coroutine_threadsafe(
            cleanup_expired_ips(db, unifi_manager), loop
        )
        try:
            # Wait up to 5 minutes for the cleanup to finish before the next
            # scheduler tick.
            future.result(timeout=300)
        except asyncio.TimeoutError:
            logger.error("Cleanup job timed out after 300 s")
        except Exception as exc:
            logger.error(
                f"Cleanup job raised an unexpected error: {exc}", exc_info=True
            )

    _scheduler = BackgroundScheduler(daemon=True)
    _scheduler.add_job(
        _job,
        trigger="interval",
        hours=interval_hours,
        id="cleanup_expired_ips",
        name="IP expiry cleanup",
        misfire_grace_time=3600,  # allow up to 1 h late start
    )
    _scheduler.start()
    logger.info(f"✅ Cleanup scheduler started — runs every {interval_hours} hour(s)")
    return _scheduler


def stop_scheduler() -> None:
    """Gracefully shut down the background scheduler, if running."""
    global _scheduler
    if _scheduler is not None and _scheduler.running:
        _scheduler.shutdown(wait=False)
        logger.info("Cleanup scheduler stopped")
    _scheduler = None
