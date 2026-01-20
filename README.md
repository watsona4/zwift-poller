# Zwift Poller

A standalone service that polls the Zwift API and sends updates to Home Assistant via webhooks. This offloads the resource-intensive API polling from Home Assistant's async loop.

## Features

- **OAuth2 token management** - Automatic refresh of access tokens
- **Change detection** - Only sends webhooks when data actually changes
- **Efficient polling** - Profile/activities poll every 5 minutes, world data every 30 seconds when riding
- **Automatic relay host discovery** - Probes multiple Zwift relay hosts to find a working one
- **Docker-ready** - Runs in a separate container from Home Assistant

## Quick Start

1. Copy `.env.example` to `.env` and fill in your credentials:
   ```bash
   cp .env.example .env
   ```

2. Edit `.env`:
   ```env
   ZWIFT_USERNAME=your_email@example.com
   ZWIFT_PASSWORD=your_password
   ZWIFT_PLAYER_ID=1234567
   ZWIFT_HA_WEBHOOK_ID=your-random-webhook-id
   ```

3. Start the container:
   ```bash
   docker compose up -d
   ```

## Configuration

### Required Environment Variables

| Variable | Description |
|----------|-------------|
| `ZWIFT_USERNAME` | Your Zwift account email |
| `ZWIFT_PASSWORD` | Your Zwift account password |
| `ZWIFT_PLAYER_ID` | Your Zwift player ID |
| `ZWIFT_HA_WEBHOOK_ID` | Webhook ID to use in Home Assistant |

### Optional Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `ZWIFT_HA_URL` | `http://homeassistant:8123` | Home Assistant base URL |
| `ZWIFT_HA_TOKEN` | (empty) | Long-lived access token for authenticated webhooks |
| `ZWIFT_PROFILE_INTERVAL` | `300` | Profile poll interval (seconds) |
| `ZWIFT_ACTIVITIES_INTERVAL` | `300` | Activities poll interval (seconds) |
| `ZWIFT_WORLD_INTERVAL` | `30` | World/live data poll interval when riding (seconds) |
| `ZWIFT_LOG_LEVEL` | `INFO` | Logging level (DEBUG, INFO, WARNING, ERROR) |

## Home Assistant Setup

1. Generate a random webhook ID (e.g., using `uuidgen` or `openssl rand -hex 16`)

2. Add to `secrets.yaml`:
   ```yaml
   zwift_webhook_id: "your-random-webhook-id-here"
   ```

3. Copy `homeassistant/zwift_webhook.yaml` to your packages directory:
   ```bash
   cp homeassistant/zwift_webhook.yaml /path/to/homeassistant/config/packages/
   ```

4. Ensure packages are loaded in `configuration.yaml`:
   ```yaml
   homeassistant:
     packages: !include_dir_named packages
   ```

5. Restart Home Assistant

## Webhook Events

The poller sends these events to Home Assistant:

| Event | Description |
|-------|-------------|
| `zwift_profile_update` | Player profile data (FTP, weight, totals, etc.) |
| `zwift_activities_update` | Recent activities list |
| `zwift_world_update` | Real-time ride data (power, HR, speed, etc.) |
| `zwift_status_update` | Online/offline status changes |

## Finding Your Player ID

Your Zwift player ID can be found:
- In your Zwift profile URL: `zwift.com/athlete/PLAYER_ID`
- Via the Zwift Companion app
- In the existing HA package's `input_number.zwift_my_player_id`

## Network Setup

The container needs to:
1. Reach Zwift servers (internet access)
2. Reach Home Assistant (on the `homeassistant` network)

The `docker-compose.yaml` assumes an external network named `homeassistant` exists. Adjust as needed for your setup.

## Migrating from HA-Native Zwift

If you're replacing an existing HA-based Zwift integration:

1. Keep your `input_number.zwift_ride_minutes_total` value (it preserves your total ride time)
2. The new package uses the same entity unique_ids, so history should be preserved
3. Disable/remove the old automations that poll Zwift APIs
4. Remove the old `rest_command` and `shell_command` entries for Zwift

## Development

```bash
# Install in development mode
pip install -e .

# Run directly
python -m zwift_poller

# Run tests
pip install -e ".[dev]"
pytest
```

## Troubleshooting

### "No working relay host found"
- Check internet connectivity
- Zwift servers may be down
- Try again in a few minutes

### Authentication failures
- Verify username/password are correct
- Check if Zwift requires you to accept new terms of service (log in via web/app first)

### Webhooks not received
- Verify `ZWIFT_HA_WEBHOOK_ID` matches `secrets.yaml`
- Check container can reach Home Assistant
- Look at HA logs for webhook errors
