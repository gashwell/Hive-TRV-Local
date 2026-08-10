# Hive TRV Local

Home Assistant custom integration for local control of Hive and Danfoss TRVs via Zigbee2MQTT.

No Hive cloud. No Hive hub. Works entirely locally over MQTT.

## Features

- **Room groups** — group multiple TRVs into a single virtual climate entity
- **Boiler demand** — automatically turn your boiler/receiver on when any TRV calls for heat
- **Schedules** — weekly heating schedules with comfort and eco presets
- **Boost** — timed boost with configurable temperature and duration
- **Lovelace cards** — auto-registered cards for individual TRVs and room groups

## Requirements

- Home Assistant 2024.1.0 or later
- Zigbee2MQTT running and connected to HA via MQTT integration
- Hive TRVs (UK7004240) paired to Zigbee2MQTT

## Installation

Install via HACS as a custom repository:

1. HACS → Integrations → ⋮ → Custom repositories
2. URL: `https://github.com/gashwell/Hive-TRV-Local-v3`
3. Category: Integration
4. Download → Restart Home Assistant

## Setup

1. Settings → Devices & Services → Add Integration → search **Hive TRV Local**
2. Enter your Zigbee2MQTT base topic (default: `zigbee2mqtt`)
3. Configure → Manage room groups → Create a new room group
4. Enter the Z2M MQTT topic for each TRV, e.g. `zigbee2mqtt/Living Room TRV`

## Adding TRVs to a group

Enter the full Zigbee2MQTT topic for each TRV — one per line or comma-separated:

```
zigbee2mqtt/Living Room TRV
zigbee2mqtt/Living Room TRV 2
```

Topics are shown as hints based on what Zigbee2MQTT has already reported to HA.
