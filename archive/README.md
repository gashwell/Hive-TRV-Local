# Hive TRV Local

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-orange.svg)](https://github.com/custom-components/hacs)
[![GitHub release](https://img.shields.io/github/release/gashwell/Hive-TRV-Local-v3.svg)](https://github.com/gashwell/Hive-TRV-Local-v3/releases)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

Local control of Hive and Danfoss TRVs and Hive receivers (SLR1/SLR2) via Zigbee2MQTT.  
No Hive cloud. No Hive hub. Fully local over MQTT.

---

## What it does

- **Per-device entries** — add each TRV and receiver individually with its Z2M MQTT topic
- **Room groups** — group TRVs into virtual room climate entities
- **Boiler demand** — turns your receiver/boiler on when any group member calls for heat
- **Schedules** — weekly heating schedules with comfort and eco presets
- **Boost** — timed boost per device or per room group
- **Lovelace cards** — auto-registered cards for individual TRVs and room groups
- **Entity suppression** — when a TRV joins a group its individual climate entity is hidden; restore it by removing from the group

---

## Supported devices

| Device | Type | Z2M model |
|---|---|---|
| Hive Radiator Valve | TRV | UK7004240 |
| Hive SLR1 / SLR1b / SLR1c / SLR1d | Receiver (single channel) | SLR1 |
| Hive SLR2 / SLR2b / SLR2c / SLR2d | Receiver (dual channel — heating + hot water) | SLR2 |
| Hive OTR1 | Receiver (standalone) | OTR1 |

Note: The Hive SLT thermostat (SLT6 etc.) exposes only a battery sensor in Z2M — it has no climate entity and does not need to be added to this integration.

---

## Requirements

- Home Assistant 2024.1.0 or later
- Zigbee2MQTT running and connected to HA via the MQTT integration
- Hive TRVs and/or receivers paired to Zigbee2MQTT

---

## Installation

### Via HACS (recommended)

1. Open HACS in HA
2. Click **⋮ → Custom repositories**
3. Add `https://github.com/gashwell/Hive-TRV-Local-v3` — category: **Integration**
4. Click **Download**
5. Restart Home Assistant

### Manual

Copy the `custom_components/hive_trv_local` folder into your HA `config/custom_components/` directory and restart.

---

## Setup

### Step 1 — Add your TRVs

**Settings → Devices & Services → Add Integration → Hive TRV Local → Add a TRV**

Enter:
- **Device name** — a friendly name, e.g. `Living Room TRV`
- **Z2M MQTT topic** — the full topic from Zigbee2MQTT, e.g. `zigbee2mqtt/Living Room TRV`

Repeat for every TRV. Each creates its own device entry with:
- `climate.*` — individual TRV climate entity
- `sensor.*` — battery and heating demand
- `number.*` — boost temperature, boost duration, frost protection

### Step 2 — Add your receiver (if applicable)

**Add Integration → Add a receiver**

Enter:
- **Device name** — e.g. `Hive Receiver`
- **Z2M MQTT topic** — e.g. `zigbee2mqtt/Hive Receiver`
- **Model** — SLR1 (single channel), SLR2 (dual channel — adds hot water control), OTR1

SLR2 creates an additional water mode select entity and water boost button.

### Step 3 — Set up the room group manager (once)

**Add Integration → Set up room group manager**

This creates a single group manager entry. Only do this once.

### Step 4 — Create room groups

**Room Groups → Configure → Manage room groups → Create a new room group**

1. Enter a room name
2. Select TRVs from the picker — only your registered TRVs appear, only those not already in a group
3. Optionally add extra temperature sensors
4. Done — a group climate entity is created and the individual TRV climate entities are hidden

### Step 5 — Configure the group manager

**Room Groups → Configure → Settings**

- **Boiler / receiver entity** — set this to your receiver's climate entity (or a switch/input_boolean). It will be turned on when any group member calls for heat.

---

## Room groups

Each room group creates:
- `climate.*` — virtual group climate entity (average temperature, fan-out commands)
- `button.*` — Boost and End Boost buttons
- `number.*` — default boost temperature and duration

### Group modes

| Mode | Description |
|---|---|
| Manual | Set a target temperature directly |
| Schedule | Follow a weekly time/temperature schedule |
| Boost | Timed boost at a set temperature, returns to previous mode when finished |
| Off | Turn all members off |

### Entity suppression

When a TRV is added to a group its individual `climate.*` entity is hidden automatically. This keeps dashboards clean — you control the TRV through the group card.

Remove the TRV from the group and the individual entity is immediately restored, no restart required.

---

## Lovelace cards

Both cards are auto-registered when the integration loads — no manual resource setup needed.

### Individual TRV card (`custom:hive-trv-card`)

```yaml
type: custom:hive-trv-card
entity: climate.living_room_trv
battery_entity: sensor.living_room_trv_battery           # optional
demand_entity: sensor.living_room_trv_pi_heating_demand  # optional
```

Features: current temperature, target temperature, mode selector (Manual/Schedule/Boost/Off), boost panel with temperature and duration sliders, schedule slot view, battery bar, heating demand bar, signal strength, valve orientation, window open toggle, frost protect.

### Room group card (`custom:hive-trv-group-card`)

```yaml
type: custom:hive-trv-group-card
entity: climate.living_room
```

Features: average temperature, group target temperature, mode selector, schedule view with current slot highlighted, heating demand bar, per-member temperature breakdown.

Both cards appear automatically in the HA 2026.6+ entity-based card picker when you add a card from a TRV or group entity page.

---

## Services

### Group services

| Service | Description |
|---|---|
| `hive_trv_local.group_boost` | Start a timed boost on a room group |
| `hive_trv_local.group_end_boost` | Cancel an active boost |
| `hive_trv_local.group_set_schedule` | Set a custom weekly schedule |
| `hive_trv_local.group_clear_schedule` | Remove the schedule (returns to manual) |
| `hive_trv_local.group_advance_schedule` | Skip immediately to the next scheduled slot |

### Schedule format

```yaml
service: hive_trv_local.group_set_schedule
data:
  entity_id: climate.living_room
  schedule:
    - days: [0, 1, 2, 3, 4]   # 0=Mon, 6=Sun
      time: "06:30"
      temperature: 21.0
    - days: [0, 1, 2, 3, 4]
      time: "09:00"
      temperature: 18.0
    - days: [5, 6]
      time: "08:00"
      temperature: 21.0
```

---

## Logging

Info-level events (device setup, room creation, boiler demand changes, boost start/end) appear in HA logs without any configuration.

For full debug output add to `configuration.yaml`:

```yaml
logger:
  default: warning
  logs:
    custom_components.hive_trv_local: debug
```

---

## Troubleshooting

**TRV not responding to commands**
- Check the Z2M MQTT topic in the device settings exactly matches what Z2M shows in its device list
- Check the MQTT integration is connected and Z2M is running
- Check the HA log for `custom_components.hive_trv_local` entries

**Room group climate entity unavailable**
- At least one member TRV must have reported state to Z2M since HA started
- Check that the TRV's individual entity exists and has a state in Developer Tools → States

**Configure button not showing**
- The integration entry must be fully loaded — check Settings → System → Logs for errors
- If upgrading from a previous version, delete all old entries first and re-add

**HACS shows "no information"**
- HACS → ⋮ → Reload data, then try again

---

## Version history

See [CHANGELOG.md](CHANGELOG.md) for full release notes.

| Version | Summary |
|---|---|
| 4.0.0 | Complete rewrite — per-device entries, entity suppression, receiver support |
| 3.1.x | MQTT topic-based member selection (superseded) |
| 2.0.x | Z2M entity detection attempts (superseded) |

---

## Credits

Receiver MQTT coordinator adapted from [andrew-codechimp/HA-Hive-Local-Thermostat](https://github.com/andrew-codechimp/HA-Hive-Local-Thermostat) (MIT licence).  
See [NOTICE](NOTICE) for full attribution.

---

## Licence

MIT — see [LICENSE](LICENSE) for details.
