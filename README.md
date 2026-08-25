# Hive TRV — HA Dashboard & Automations

Standard Home Assistant setup for 11 Hive TRVs (UK7004240) via Zigbee2MQTT
and a Sonoff ZBMINIR2 relay as the boiler demand switch.

No custom integration required — uses native Z2M climate entities.

---

## Files

### `heating_dashboard.yaml`
Three-view Lovelace dashboard:
- **Heating** — boiler status tile, living room group thermostat, individual
  TRV cards with red flame badge (Mushroom Cards + card_mod) when heating
- **TRV Settings** — all Hive-controllable settings per TRV: programme mode,
  keypad lock, window detection, calibration offset, max temp, orientation,
  summer mode, adaptation run
- **Diagnostics** — logbook showing which TRV triggered heat and when,
  boiler on/off history graph, TRV heat demand history, battery levels

**Requirements:** Mushroom Cards + card_mod (both via HACS → Frontend)

**To install:**
1. Settings → Dashboards → Add dashboard → Title: Heating, URL: heating,
   tick Show in sidebar
2. Open dashboard → Edit → Raw configuration editor → paste file contents

### `boiler_automation.yaml`
Two automations (separated by `---`):
- **Boiler ON** — fires immediately when any TRV reports `hvac_action: heating`
- **Boiler OFF** — waits 5 minutes after all TRVs go idle, re-checks demand,
  aborts if switch was manually turned on during hold-off

Manual toggle of `switch.boiler_switch` is never overridden.

**To install:** Settings → Automations → ⋮ → Edit as YAML — import each
automation separately (file contains two, split by `---`)

### `heating_log_automation.yaml`
Parallel automation that writes readable logbook entries for every TRV
demand change:
- `TV Radiator requesting heat — room 19.2°C, target 21°C, demand 74%`
- `TV Radiator satisfied — room 21.1°C, target 21°C`

Entries appear in the Diagnostics logbook card.

**To install:** Settings → Automations → ⋮ → Edit as YAML → paste and save

---

## TRVs

| Entity | Room |
|---|---|
| `climate.hive_trv_group_living_room` | Living room group (TV + Bay + Dining) |
| `climate.hive_trv_tv` | TV radiator |
| `climate.hive_trv_bay` | Bay radiator |
| `climate.hive_trv_dining` | Dining radiator |
| `climate.hive_trv_bedroom` | Bedroom |
| `climate.hive_trv_kitchen` | Kitchen |
| `climate.hive_trv_office` | Office |
| `climate.hive_trv_hallway` | Hallway |
| `climate.hive_trv_entrance` | Entrance |
| `climate.hive_trv_guestroom` | Guest room |
| `climate.hive_trv_conservatory` | Conservatory |
| `climate.hive_trv_garage` | Garage |

## Boiler switch

`switch.boiler_switch` — Sonoff ZBMINIR2 relay switching the 230V RT circuit
on the Vaillant ecoFIT Pure.
