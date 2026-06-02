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

Enter your Zigbee2MQTT base topic (default: `zigbee2mqtt`). TRVs appear automatically within 30 seconds as Z2M publishes device data. No need to list device names.

---

## Configuration

**Settings → Integrations → Hive Local TRV → Configure**

The Configure menu has two sections:

### Device settings

| Option | Description |
|---|---|
| Boiler / receiver entity | HA entity turned on/off based on aggregate TRV heat demand. Supports `climate`, `switch`, and `input_boolean`. |
| People to track for geofencing | When all selected people leave home, all TRVs drop to frost protection automatically. |
| Enable diagnostic logging | Writes `HIVE_DIAG` entries to the HA log at WARNING level. Search for `HIVE_DIAG` in Settings → System → Logs → Load Full Log. |

### Manage room groups

Room groups let you control multiple TRVs together as a single climate entity. The group shows the average temperature across all its members and fans out all commands (mode, temperature, boost, schedule) to every member simultaneously.

**When a TRV is added to a group its individual climate entity is removed from the main page.** Its sensor entities (battery, temperature, heating demand) remain visible under the TRV's own device card so you can still see per-device readings.

#### Create a room group (3 steps)

1. **Name** — enter a room name, e.g. `Living Room`
2. **Devices** — pick from a dropdown of all discovered TRVs. Only devices not already in another group are shown. Each device can belong to only one group.
3. **Extra temperature sensors** (optional) — additional HA temperature sensor entities to include in the room average

A new `climate.living_room` entity appears immediately — no restart required.

#### Edit a room group (2 steps)

1. **Select group** — pick from existing groups
2. **Members** — current members are pre-ticked. Tick ungrouped TRVs to add them. Untick current members to remove them.

Changes take effect immediately. Removed members regain their individual climate entities. Added members have their individual climate entities suppressed.

#### Remove a room group

Select from a dropdown of existing groups. All members regain their individual climate entities immediately.

---

## Entities created

### Per TRV (ungrouped)

| Platform | Entity | Notes |
|---|---|---|
| `climate` | Main control | Temperature, mode, presets. Hidden when TRV is in a group. |
| `sensor` | Battery | Always visible — even when grouped |
| `sensor` | Heating demand | PI demand 0–100%. Always visible. |
| `number` | Setpoint offset | ±2.5 °C calibration |
| `number` | Boost temperature | Default boost target |
| `number` | Boost duration | Default boost duration (minutes) |
| `select` | Keypad lock | unlock / lock1 / lock2 |
| `button` | Run adaptation | Valve calibration routine |
| `button` | Enter mounting mode | For valve re-installation |

### Per room group

| Platform | Entity | Notes |
|---|---|---|
| `climate` | Group control | Average temperature; commands fan out to all members |

The group climate entity's `extra_state_attributes` include `members` (list of TRV names), `member_count`, and when boosting, `boost_ends` and `boost_remaining_minutes`.

---

## Climate modes

| Mode | Behaviour |
|---|---|
| `manual` | Hold a fixed setpoint indefinitely |
| `schedule` | HA manages a weekly schedule and pushes setpoints |
| `boost` | Timed override at a configurable temperature; previous mode restores on expiry |
| HVAC off | Drops to frost protection temperature (7 °C default) |

All modes work identically on individual TRV entities and room group entities.

---

## Services

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

Schedules are set via the `set_schedule` service on either a TRV or a room group entity. Each slot needs `days` (0 = Monday, 6 = Sunday), `time` (HH:MM), and `temperature` (°C):

```yaml
service: hive_local_trv.set_schedule
data:
  entity_id: climate.living_room
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

When applied to a room group entity the schedule is fanned out to all member TRVs.

---

## Updates via HACS

Update in HACS, then **restart Home Assistant**. Existing configuration and room groups are preserved automatically — no need to remove and re-add the integration.

---

## Troubleshooting

**TRVs not appearing** — check Z2M is running and publishing to the correct base topic. TRVs appear within 30 seconds of Z2M publishing its device list.

**My TRV climate entity has disappeared** — it is in a room group. The group climate entity (`climate.room_name`) is the control point. Individual sensor entities remain visible under the TRV device card.

**Room group devices not available in dropdown** — a device already in a group will not appear. Edit the group it belongs to and remove it first.

**Diagnostic logging** — enable via Configure → Device settings → Enable diagnostic logging. Search for `HIVE_DIAG` in Settings → System → Logs → Load Full Log.

---

## License

MIT
