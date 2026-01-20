"""Configuration management using pydantic-settings."""

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_prefix="ZWIFT_",
        env_file=".env",
        env_file_encoding="utf-8",
    )

    # Zwift credentials
    username: str = Field(description="Zwift account username/email")
    password: str = Field(description="Zwift account password")
    player_id: int = Field(description="Your Zwift player ID")

    # Home Assistant webhook
    ha_url: str = Field(
        default="http://homeassistant:8123",
        description="Home Assistant base URL",
    )
    ha_webhook_id: str = Field(description="Webhook ID configured in Home Assistant")
    ha_token: str = Field(
        default="",
        description="Home Assistant long-lived access token (optional, for authenticated webhooks)",
    )

    # Polling intervals (seconds)
    profile_interval: int = Field(
        default=300,
        description="Profile data poll interval (seconds)",
    )
    activities_interval: int = Field(
        default=300,
        description="Activities data poll interval (seconds)",
    )
    world_interval: int = Field(
        default=30,
        description="World/live data poll interval when riding (seconds)",
    )

    # Token refresh margin (seconds before expiry to refresh)
    token_refresh_margin: int = Field(
        default=60,
        description="Refresh tokens this many seconds before expiry",
    )

    # Relay hosts to try
    relay_hosts: list[str] = Field(
        default=[
            "us-or-rly101.zwift.com",
            "us-or-rly102.zwift.com",
            "eu-west-rly101.zwift.com",
            "eu-west-rly102.zwift.com",
        ],
        description="List of Zwift relay hosts to try",
    )

    # Token storage path
    token_file: str = Field(
        default="/data/tokens.json",
        description="Path to store OAuth tokens",
    )

    # Logging
    log_level: str = Field(
        default="INFO",
        description="Logging level",
    )


def get_settings() -> Settings:
    """Get application settings."""
    return Settings()
