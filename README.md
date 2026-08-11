# Hive Local

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-orange.svg)](https://github.com/custom-components/hacs)
[![GitHub release](https://img.shields.io/github/release/gashwell/Hive-TRV-Local.svg)](https://github.com/gashwell/Hive-TRV-Local/releases)

Fully local control of your Hive heating system via Zigbee2MQTT.  
**No Hive cloud. No Hive hub. Everything runs on your local network.**

Replaces the full Hive app experience locally — TRV control, receiver/boiler control,
room grouping, schedules, boost, and frost protection.

---

## Features

- **TRV control** — set temperature, mode, boost per radiator
- **Receiver control** — SLR1 / SLR2 / OTR1 via Z2M
- **Room groups** — group multiple TRVs into one heating zone
  - Average temperature across all TRVs (+ optional wall sensors)
  - Any TRV demanding heat fires the boiler
  - Individual TRV entities hidden while in a room, restored when removed
- **UI Scheduler** — weekly schedule built into the room card
- **Boost** — timed, per device or per room, returns to schedule after
- **Frost protection** — optional Open-Meteo weather-based anti-freeze

---

## Requirements

- Home Assistant 2024.1.0+
- Zigbee2MQTT running and connected via MQTT integration
- Hive TRVs and/or receivers paired to Zigbee2MQTT

---

## Installation

1. HACS → ⋮ → Custom repositories → `https://github.com/gashwell/Hive-TRV-Local`
2. Download → Restart HA
3. Settings → Devices & Services → Add Integration → **Hive Local**

## Setup

1. Enter your Z2M base topic (default: `zigbee2mqtt`)
2. **Configure → Devices → Add a TRV** — select from detected or enter topic
3. Repeat for all TRVs and your receiver
4. **Configure → Rooms → Create a room** — name it, pick TRVs, done
5. **Configure → Settings** — set your receiver as the boiler entity

---

## History

All previous versions (v1–v4) are preserved in the `archive/` folder of this repo.
