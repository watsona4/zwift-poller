"""Main entry point for zwift-poller."""

import asyncio
import logging
import signal
import sys

from .config import get_settings
from .poller import run_poller


def setup_logging(level: str) -> None:
    """Configure logging."""
    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    # Reduce noise from aiohttp
    logging.getLogger("aiohttp").setLevel(logging.WARNING)


def main() -> None:
    """Main entry point."""
    try:
        settings = get_settings()
    except Exception as e:
        print(f"Configuration error: {e}", file=sys.stderr)
        print("\nRequired environment variables:", file=sys.stderr)
        print("  ZWIFT_USERNAME - Zwift account email", file=sys.stderr)
        print("  ZWIFT_PASSWORD - Zwift account password", file=sys.stderr)
        print("  ZWIFT_PLAYER_ID - Your Zwift player ID", file=sys.stderr)
        print("  ZWIFT_HA_WEBHOOK_ID - Home Assistant webhook ID", file=sys.stderr)
        print("\nOptional environment variables:", file=sys.stderr)
        print("  ZWIFT_HA_URL - Home Assistant URL (default: http://homeassistant:8123)", file=sys.stderr)
        print("  ZWIFT_HA_TOKEN - Home Assistant access token", file=sys.stderr)
        print("  ZWIFT_PROFILE_INTERVAL - Profile poll interval in seconds (default: 300)", file=sys.stderr)
        print("  ZWIFT_ACTIVITIES_INTERVAL - Activities poll interval in seconds (default: 300)", file=sys.stderr)
        print("  ZWIFT_WORLD_INTERVAL - World poll interval when riding (default: 30)", file=sys.stderr)
        print("  ZWIFT_LOG_LEVEL - Logging level (default: INFO)", file=sys.stderr)
        sys.exit(1)

    setup_logging(settings.log_level)
    logger = logging.getLogger(__name__)

    logger.info("Starting zwift-poller")
    logger.info("  Player ID: %d", settings.player_id)
    logger.info("  HA URL: %s", settings.ha_url)
    logger.info("  Profile interval: %ds", settings.profile_interval)
    logger.info("  Activities interval: %ds", settings.activities_interval)
    logger.info("  World interval: %ds", settings.world_interval)

    # Set up signal handlers for graceful shutdown
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    def handle_signal(sig: signal.Signals) -> None:
        logger.info("Received signal %s, shutting down...", sig.name)
        loop.stop()

    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, handle_signal, sig)

    try:
        loop.run_until_complete(run_poller(settings))
    except KeyboardInterrupt:
        logger.info("Interrupted by user")
    finally:
        loop.close()
        logger.info("Shutdown complete")


if __name__ == "__main__":
    main()
