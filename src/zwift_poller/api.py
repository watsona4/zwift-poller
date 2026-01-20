"""Zwift API client."""

import logging
from dataclasses import dataclass
from typing import Any

import aiohttp

from . import zwift_messages_pb2 as zmsg

logger = logging.getLogger(__name__)

# World ID to name mapping
WORLD_MAP = {
    1: "watopia",
    2: "richmond",
    3: "london",
    4: "new-york",
    5: "innsbruck",
    6: "bologna",
    7: "yorkshire",
    8: "crit-city",
    9: "makuri-islands",
    10: "france",
    11: "paris",
    13: "scotland",
}


@dataclass
class ZwiftAPI:
    """Zwift API client."""

    relay_hosts: list[str]
    _session: aiohttp.ClientSession | None = None
    _active_host: str | None = None

    async def __aenter__(self):
        """Async context manager entry."""
        self._session = aiohttp.ClientSession()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        if self._session:
            await self._session.close()
            self._session = None

    def _api_url(self, path: str) -> str:
        """Build API URL using active relay host."""
        host = self._active_host or self.relay_hosts[0]
        return f"https://{host}{path}"

    async def probe_relay_hosts(self, token: str, player_id: int) -> str | None:
        """Find a working relay host.

        Returns the first host that responds successfully, or None.
        """
        if not self._session:
            return None

        for host in self.relay_hosts:
            try:
                url = f"https://{host}/api/profiles/{player_id}"
                async with self._session.get(
                    url,
                    headers={
                        "Authorization": f"Bearer {token}",
                        "Accept": "application/json",
                    },
                    timeout=aiohttp.ClientTimeout(total=10),
                ) as resp:
                    if resp.status == 200:
                        logger.info("Found working relay host: %s", host)
                        self._active_host = host
                        return host
                    else:
                        logger.debug("Host %s returned %d", host, resp.status)
            except Exception as e:
                logger.debug("Host %s failed: %s", host, e)
                continue

        logger.warning("No working relay host found")
        return None

    async def get_profile(self, token: str, player_id: int) -> dict[str, Any] | None:
        """Fetch player profile data."""
        if not self._session:
            return None

        url = self._api_url(f"/api/profiles/{player_id}")
        try:
            async with self._session.get(
                url,
                headers={
                    "Authorization": f"Bearer {token}",
                    "Accept": "application/json",
                },
                timeout=aiohttp.ClientTimeout(total=30),
            ) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    logger.debug("Profile fetched successfully")
                    return data
                else:
                    text = await resp.text()
                    logger.warning("Profile fetch failed: %d - %s", resp.status, text)
                    return None
        except Exception as e:
            logger.error("Profile fetch error: %s", e)
            return None

    async def get_activities(
        self, token: str, player_id: int, start: int = 0, limit: int = 10
    ) -> list[dict[str, Any]] | None:
        """Fetch player activities."""
        if not self._session:
            return None

        url = self._api_url(f"/api/profiles/{player_id}/activities?start={start}&limit={limit}")
        try:
            async with self._session.get(
                url,
                headers={
                    "Authorization": f"Bearer {token}",
                    "Accept": "application/json",
                },
                timeout=aiohttp.ClientTimeout(total=30),
            ) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    logger.debug("Activities fetched: %d items", len(data) if isinstance(data, list) else 0)
                    return data if isinstance(data, list) else []
                else:
                    text = await resp.text()
                    logger.warning("Activities fetch failed: %d - %s", resp.status, text)
                    return None
        except Exception as e:
            logger.error("Activities fetch error: %s", e)
            return None

    async def get_world_status(
        self, token: str, world_id: int, player_id: int
    ) -> dict[str, Any] | None:
        """Fetch real-time player status from world relay.

        Returns parsed protobuf data as dict, or None on failure.
        """
        if not self._session:
            return None

        url = self._api_url(f"/relay/worlds/{world_id}/players/{player_id}")

        # Try different Accept headers as some relays prefer different ones
        accepts = [
            "application/octet-stream",
            "application/x-protobuf",
            "application/vnd.google.protobuf",
            "*/*",
        ]

        for accept in accepts:
            try:
                async with self._session.get(
                    url,
                    headers={
                        "Authorization": f"Bearer {token}",
                        "Accept": accept,
                        "User-Agent": "ZwiftMobileLink/5.0 (HA)",
                    },
                    timeout=aiohttp.ClientTimeout(total=10),
                ) as resp:
                    if resp.status == 200:
                        content = await resp.read()
                        return self._parse_player_state(content)
                    else:
                        logger.debug("World status failed with Accept=%s: %d", accept, resp.status)
            except Exception as e:
                logger.debug("World status error with Accept=%s: %s", accept, e)
                continue

        logger.warning("World status fetch failed for all Accept types")
        return None

    def _parse_player_state(self, content: bytes) -> dict[str, Any]:
        """Parse protobuf PlayerState into dict."""
        ps = zmsg.PlayerState()
        ps.ParseFromString(content)

        speed_mps = ps.speed / 1_000_000.0
        speed_kmh = speed_mps * 3.6
        speed_mph = speed_mps * 2.23694
        cadence_rpm = int((ps.cadenceUHz * 60) / 1_000_000)
        altitude_m = (float(ps.altitude) - 9000.0) / 2.0
        altitude_ft = altitude_m * 3.28084
        distance_m = float(ps.distance)
        distance_mi = distance_m * 0.000621371

        return {
            "id": ps.id,
            "distance_m": distance_m,
            "distance_mi": round(distance_mi, 2),
            "speed_mps": round(speed_mps, 2),
            "speed_kmh": round(speed_kmh, 1),
            "speed_mph": round(speed_mph, 1),
            "heartrate": int(ps.heartrate),
            "power": int(ps.power),
            "cadence": cadence_rpm,
            "altitude_m": round(altitude_m, 1),
            "altitude_ft": round(altitude_ft, 0),
            "world_time": int(ps.worldTime),
            "just_watching": int(ps.justWatching),
            "calories": int(ps.calories),
            "climbing": ps.climbing,
            "gradient": round(ps.climbing / 10000.0, 1) if ps.climbing else 0.0,
            "customization_id": ps.customisationId,
            "group_id": ps.groupId,
            "heading": ps.heading,
            "laps": ps.laps,
            "lean": ps.lean,
            "progress": ps.progress,
            "road_position": ps.roadPosition,
            "road_time": ps.roadTime,
            "sport": ps.sport,
            "time": ps.time,
            "watching_rider_id": ps.watchingRiderId,
            "x": ps.x,
            "y": ps.y,
        }

    @staticmethod
    def get_world_name(world_id: int) -> str:
        """Get world name from ID."""
        return WORLD_MAP.get(world_id, f"world-{world_id}")
