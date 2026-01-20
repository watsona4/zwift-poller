"""Main polling orchestration with change detection."""

import asyncio
import hashlib
import json
import logging
from dataclasses import dataclass, field
from typing import Any

from .api import ZwiftAPI
from .auth import AuthManager
from .config import Settings
from .webhook import WebhookClient

logger = logging.getLogger(__name__)


def _compute_hash(data: Any) -> str:
    """Compute hash of data for change detection."""
    serialized = json.dumps(data, sort_keys=True, default=str)
    return hashlib.sha256(serialized.encode()).hexdigest()[:16]


@dataclass
class PollerState:
    """Tracks poller state for change detection."""

    profile_hash: str = ""
    activities_hash: str = ""
    world_hash: str = ""
    is_riding: bool = False
    world_id: int = 1
    last_profile: dict[str, Any] = field(default_factory=dict)
    last_activities: list[dict[str, Any]] = field(default_factory=list)
    last_world: dict[str, Any] = field(default_factory=dict)


class Poller:
    """Main polling orchestrator."""

    def __init__(
        self,
        settings: Settings,
        auth: AuthManager,
        api: ZwiftAPI,
        webhook: WebhookClient,
    ):
        self.settings = settings
        self.auth = auth
        self.api = api
        self.webhook = webhook
        self.state = PollerState()
        self._running = False
        self._tasks: list[asyncio.Task] = []

    async def start(self) -> None:
        """Start the poller."""
        logger.info("Starting Zwift poller")
        self._running = True

        # Ensure we have a valid token
        token = await self.auth.ensure_valid_token()
        if not token:
            logger.error("Failed to authenticate - check credentials")
            return

        # Find a working relay host
        host = await self.api.probe_relay_hosts(token, self.settings.player_id)
        if not host:
            logger.warning("No working relay host found, will retry on next poll")

        # Initial fetch and send (always send on startup)
        await self._poll_profile(force_send=True)
        await self._poll_activities(force_send=True)

        # Start polling tasks
        self._tasks = [
            asyncio.create_task(self._profile_loop()),
            asyncio.create_task(self._activities_loop()),
            asyncio.create_task(self._world_loop()),
        ]

        # Wait for all tasks
        try:
            await asyncio.gather(*self._tasks)
        except asyncio.CancelledError:
            logger.info("Poller tasks cancelled")

    async def stop(self) -> None:
        """Stop the poller."""
        logger.info("Stopping Zwift poller")
        self._running = False
        for task in self._tasks:
            task.cancel()

    async def _profile_loop(self) -> None:
        """Poll profile data at configured interval."""
        while self._running:
            await asyncio.sleep(self.settings.profile_interval)
            await self._poll_profile()

    async def _activities_loop(self) -> None:
        """Poll activities data at configured interval."""
        while self._running:
            await asyncio.sleep(self.settings.activities_interval)
            await self._poll_activities()

    async def _world_loop(self) -> None:
        """Poll world data at configured interval when riding."""
        while self._running:
            if self.state.is_riding:
                await self._poll_world()
                await asyncio.sleep(self.settings.world_interval)
            else:
                # Check less frequently when not riding
                await asyncio.sleep(60)

    async def _poll_profile(self, force_send: bool = False) -> None:
        """Poll and process profile data."""
        token = await self.auth.ensure_valid_token()
        if not token:
            logger.warning("No valid token for profile poll")
            return

        data = await self.api.get_profile(token, self.settings.player_id)
        if data is None:
            return

        # Check for riding status change
        was_riding = self.state.is_riding
        self.state.is_riding = data.get("riding", False)
        if data.get("worldId"):
            self.state.world_id = data["worldId"]

        # Log riding status changes
        if self.state.is_riding and not was_riding:
            logger.info("Rider is now online (world %d)", self.state.world_id)
            await self.webhook.send_status(True, self.state.world_id)
        elif not self.state.is_riding and was_riding:
            logger.info("Rider is now offline")
            await self.webhook.send_status(False)

        # Check for data change
        data_hash = _compute_hash(data)
        if force_send or data_hash != self.state.profile_hash:
            logger.info("Profile data changed, sending webhook")
            self.state.profile_hash = data_hash
            self.state.last_profile = data
            await self.webhook.send_profile(data)
        else:
            logger.debug("Profile data unchanged")

    async def _poll_activities(self, force_send: bool = False) -> None:
        """Poll and process activities data."""
        token = await self.auth.ensure_valid_token()
        if not token:
            logger.warning("No valid token for activities poll")
            return

        data = await self.api.get_activities(token, self.settings.player_id)
        if data is None:
            return

        # Check for data change
        data_hash = _compute_hash(data)
        if force_send or data_hash != self.state.activities_hash:
            logger.info("Activities data changed, sending webhook")
            self.state.activities_hash = data_hash
            self.state.last_activities = data
            await self.webhook.send_activities(data)
        else:
            logger.debug("Activities data unchanged")

    async def _poll_world(self) -> None:
        """Poll and process world/live data."""
        if not self.state.is_riding:
            return

        token = await self.auth.ensure_valid_token()
        if not token:
            logger.warning("No valid token for world poll")
            return

        data = await self.api.get_world_status(
            token, self.state.world_id, self.settings.player_id
        )
        if data is None:
            return

        # For world data, we typically want to send every update when riding
        # but we can still skip if completely unchanged
        data_hash = _compute_hash(data)
        if data_hash != self.state.world_hash:
            logger.debug("World data changed, sending webhook")
            self.state.world_hash = data_hash
            self.state.last_world = data
            await self.webhook.send_world(data)


async def run_poller(settings: Settings) -> None:
    """Run the poller with all components."""
    async with AuthManager(
        username=settings.username,
        password=settings.password,
        token_file=settings.token_file,
        refresh_margin=settings.token_refresh_margin,
    ) as auth:
        async with ZwiftAPI(relay_hosts=settings.relay_hosts) as api:
            async with WebhookClient(
                ha_url=settings.ha_url,
                webhook_id=settings.ha_webhook_id,
                token=settings.ha_token,
            ) as webhook:
                poller = Poller(settings, auth, api, webhook)
                await poller.start()
