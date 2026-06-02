# Hive Local TRV

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-orange.svg)](https://github.com/hacs/integration)
[![HA Version](https://img.shields.io/badge/Home%20Assistant-2024.1%2B-blue)](https://www.home-assistant.io/)
[![Release](https://img.shields.io/github/v/release/gashwell/Hive-TRV-Local)](https://github.com/gashwell/Hive-TRV-Local/releases)

Local Home Assistant integration for **Hive UK7004240 / TRV001 radiator valves** via Zigbee2MQTT.  
No Hive cloud. No subscription. Full local control.

---

## Requirements

- Home Assistant 2024.1 or newer
- Zigbee2MQTT with your TRVs already paired
- MQTT broker (Mosquitto add-on or external)
- The HA **MQTT** integration configured

---

## Installation

### Via HACS (recommended)

1. HACS → Integrations → ⋮ → **Custom repositories**
2. Add `https://github.com/gashwell/Hive-TRV-Local` — type **Integration**
3. Install **Hive Local TRV** and restart Home Assistant

### Manual

Copy `custom_components/hive_local_trv/` into your HA `config/custom_components/` directory and restart.

---

## Setup

**Settings → Integrations → Add Integration → Hive Local TRV**

Enter your Zigbee2MQTT base topic (default: `zigbee2mqtt`). That's it — TRVs appear automatically within 30 seconds as Z2M publishes device data. No need to list device names.

---

## Configuration (after install)

**Settings → Integrations → Hive Local TRV → Configure**

A menu presents two sections:

### Device settings

| Option | Description |
|---|---|
| Boiler / receiver entity | HA entity turned on/off based on aggregate TRV heat demand. Supports `climate`, `switch`, and `input_boolean`. |
| People to track for geofencing | When all selected people leave home, all TRVs drop to frost protection automatically. |
| Enable diagnostic logging | Writes `HIVE_DIAG` entries to the HA log at WARNING level. Useful for troubleshooting — disable once everything is working. |

### Manage room groups

Create virtual room groups that control multiple TRVs together as a single climate entity.

**Add a room group** — a 3-step wizard:

1. **Room name** — e.g. `Living Room`
2. **Devices** — pick TRVs from a dropdown showing all discovered devices. Only devices not already in another group are shown. One device can only belong to one group.
3. **Extra temperature sensors** (optional) — HA temperature sensor entities to include in the room's average temperature calculation alongside the TRV readings

The resulting `climate.living_room` entity controls all TRVs in the group simultaneously and shows the average temperature.

**Remove a room group** — select from a dropdown of existing rooms. Individual TRV entities are not affected.

Changes take effect immediately — no restart required.

---

## Entities created

Each discovered TRV gets the following entities:

| Platform | Entity | Notes |
|---|---|---|
| `climate` | Main control | Temperature, mode, presets |
| `sensor` | Battery | % |
| `sensor` | Heating demand | PI demand 0–100% |
| `number` | Setpoint offset | ±2.5 °C calibration |
| `number` | Boost temperature | Default boost target |
| `number` | Boost duration | Default boost duration (minutes) |
| `select` | Keypad lock | unlock / lock1 / lock2 |
| `button` | Run adaptation | Valve calibration routine |
| `button` | Enter mounting mode | For valve re-installation |

Room groups create an additional `climate` entity per group.

---

## Climate modes

The TRV climate entity supports the following preset modes:

| Mode | Behaviour |
|---|---|
| `manual` | Hold a fixed setpoint indefinitely |
| `schedule` | HA manages a weekly schedule, pushes setpoints to the TRV |
| `boost` | Timed override at a configurable temperature; restores previous mode on expiry |
| HVAC off | Drops to frost protection temperature (7 °C default) |

Away and holiday modes are applied globally across all TRVs via services.

---

## Services

All services are available in **Settings → Developer Tools → Services**.

### TRV / room group services

| Service | Description |
|---|---|
| `hive_local_trv.boost` | Start a timed boost on a TRV or room group |
| `hive_local_trv.end_boost` | Cancel an active boost |
| `hive_local_trv.set_schedule` | Set a weekly heating schedule |
| `hive_local_trv.clear_schedule` | Remove the schedule |
| `hive_local_trv.advance_schedule` | Skip to the next scheduled slot immediately |

### Whole-home services

| Service | Description |
|---|---|
| `hive_local_trv.set_holiday` | Frost protection for a date range; all TRVs restore automatically on return |
| `hive_local_trv.cancel_holiday` | Cancel an active or pending holiday |

### Room group services (alternative to UI)

| Service | Description |
|---|---|
| `hive_local_trv.add_room` | Create a room group via service call |
| `hive_local_trv.remove_room` | Remove a room group via service call |

---

## Schedule format

Schedules are set via the `set_schedule` service. Each entry needs `days` (0 = Monday, 6 = Sunday), `time` (HH:MM), and `temperature` (°C):

```yaml
service: hive_local_trv.set_schedule
data:
  entity_id: climate.living_room_trv
  schedule:
    - days: [0, 1, 2, 3, 4]
      time: "06:30"
      temperature: 21.0
    - days: [0, 1, 2, 3, 4]
      time: "09:00"
      temperature: 18.0
    - days: [0, 1, 2, 3, 4]
      time: "17:00"
      temperature: 21.0
    - days: [0, 1, 2, 3, 4]
      time: "22:00"
      temperature: 16.0
    - days: [5, 6]
      time: "08:00"
      temperature: 21.0
    - days: [5, 6]
      time: "23:00"
      temperature: 16.0
```

---

## Updates via HACS

Update to a new version in HACS, then **restart Home Assistant**. The existing configuration is preserved — no need to remove and re-add the integration. New config fields added in any release are backfilled with sensible defaults automatically.

---

## Troubleshooting

**TRVs not appearing** — check that Z2M is running and publishing to the correct base topic. TRVs appear within 30 seconds of Z2M publishing its device list.

**Diagnostic logging** — enable via Configure → Device settings → Enable diagnostic logging. Search for `HIVE_DIAG` in Settings → System → Logs → Load Full Log.

**Room group devices not available** — a device already in a group won't appear in the Add room wizard. Remove the device from its current group first.

---

## License

MIT
