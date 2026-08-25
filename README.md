# Hive TRV Heating — Home Assistant Dashboard & Automations

Local heating control for 11 Hive TRVs (UK7004240) via Zigbee2MQTT and a
Sonoff ZBMINIR2 relay as the boiler demand switch. No cloud dependency, no
custom integration — built entirely on native HA entities created by Z2M.

---

## Hardware

| Device | Purpose | HA entity |
|---|---|---|
| Hive TRV UK7004240 × 11 | Radiator valve control | `climate.hive_trv_*` |
| Sonoff ZBMINIR2 | Boiler demand switch (230V RT) | `switch.boiler_switch` |
| Vaillant ecoFIT Pure | Boiler | — controlled via RT circuit |

The ZBMINIR2 replaces the Hive SLR2c receiver. It switches the 230V room
thermostat (RT) circuit on the boiler — when the switch closes, the boiler
fires. When it opens, the boiler returns to its own internal control.

---

## TRV layout

| Entity | Room | Group |
|---|---|---|
| `climate.hive_trv_group_living_room` | Living room | Group entity — controls TV, Bay, Dining together |
| `climate.hive_trv_tv` | TV radiator | Living room group |
| `climate.hive_trv_bay` | Bay radiator | Living room group |
| `climate.hive_trv_dining` | Dining radiator | Living room group |
| `climate.hive_trv_bedroom` | Bedroom | Individual |
| `climate.hive_trv_kitchen` | Kitchen | Individual |
| `climate.hive_trv_office` | Office | Individual |
| `climate.hive_trv_hallway` | Hallway | Individual |
| `climate.hive_trv_entrance` | Entrance | Individual |
| `climate.hive_trv_guestroom` | Guest room | Individual |
| `climate.hive_trv_conservatory` | Conservatory | Individual |
| `climate.hive_trv_garage` | Garage | Individual |

**How the living room group works:** The group entity sets a shared schedule,
target temperature and mode for all three TRVs together. Each TRV still
controls its own valve independently based on its local temperature reading —
the group is for configuration only, not for demand signalling.

---

## Files

### `boiler_automation.yaml`

Two automations that control `switch.boiler_switch`:

**Boiler ON** (`mode: single`)
- Triggers immediately when any of the 11 individual TRV climate entities
  reports `hvac_action: heating`
- No delay — the boiler fires the moment the first valve opens

**Boiler OFF** (`mode: restart`)
- Triggers when any TRV leaves the heating state
- Checks immediately that no other TRV is still heating
- Waits **3 minutes** (hold-off to prevent short-cycling)
- Re-checks after the hold-off — if any TRV started heating again during
  the 3 minutes, or the switch was manually turned on, the automation aborts
- Only turns the boiler off if all TRVs are still satisfied after the hold-off

**Manual override:** Tapping the boiler switch tile on the dashboard turns it
on or off immediately. The automation never overrides a manual action.

**Why 3 minutes?** The Vaillant ecoFIT Pure has a minimum burner run time of
approximately 2 minutes. Short-cycling (firing for less than this) wastes gas
and causes wear. 3 minutes gives a comfortable margin. The residual heat in
the heat exchanger also continues circulating through radiators for a few
minutes after the burner stops, so the 3-minute hold-off also recovers that
stored heat rather than wasting it.

### `heating_log_automation.yaml`

Runs in parallel for all 11 TRVs. Writes a readable `logbook.log` entry
every time a TRV starts or stops heating:

```
Heating demand — TV Radiator requesting heat — room 19.2°C, target 21°C, demand 74%
Heating demand — TV Radiator satisfied — room 21.1°C, target 21°C
```

Entries appear in the Diagnostics view logbook card, giving a full history
of which TRV triggered each boiler run.

### `heating_dashboard.yaml`

Three-view Lovelace dashboard.

**Requirements before importing:**
- [Mushroom Cards](https://github.com/piitaya/lovelace-mushroom) — HACS → Frontend
- [card-mod](https://github.com/thomasloven/lovelace-card-mod) — HACS → Frontend

#### View 1 — Heating

- **Boiler tile** — shows ON/OFF state, tap to toggle manually
- **Living room thermostat** — single card controls all three TRVs together
  (shared schedule, target temp, mode)
- **Living room TRVs** — three individual Mushroom climate cards showing each
  radiator's current temperature and target. A red 🔥 flame badge appears on
  the card when that valve is actively heating
- **Individual rooms** — Mushroom climate card per TRV with +/− temperature
  control and flame badge when heating

#### View 2 — TRV Settings

One entities card per TRV exposing every setting controllable in the Hive app:

| Setting | Entity type | Description |
|---|---|---|
| Temperature / mode | `climate` | Current temp, target, heat/off |
| Programme mode | `select` | Manual / Schedule / Schedule with pre-heat / Eco |
| Keypad lock | `select` | Lock/unlock physical buttons on the TRV |
| Window open detection | `switch` | Enable/disable auto window detection |
| Window open override | `switch` | Manually tell the TRV the window is open |
| Heat available | `switch` | Off = summer mode (valve won't open) |
| Radiator covered | `switch` | Room sensor mode vs auto offset mode |
| Orientation | `switch` | Vertical/horizontal (affects PID algorithm) |
| Display upside-down | `switch` | Flip the screen direction |
| Temperature calibration | `number` | Offset −2.5°C to +2.5°C in 0.1° steps |
| Max temperature limit | `number` | Upper limit for the target setpoint |
| Control aggressiveness | `number` | Algorithm scale factor 1 (fast) to 10 (slow) |
| Auto adaptation run | `switch` | Enable nightly automatic calibration |
| Adaptation run control | `select` | Manually initiate or cancel an adaptation run |
| Heat required | `binary_sensor` | TRV reporting it needs heat from boiler |
| Preheat status | `binary_sensor` | TRV currently in pre-heat mode |

#### View 3 — Diagnostics

- **Heating demand log** — logbook card showing all 11 TRV climate entities
  and the boiler switch. Combined with the log automation this shows exactly
  which TRV triggered each boiler run, with room temperature and demand %
- **Boiler history graph** — 24-hour on/off timeline for `switch.boiler_switch`
- **TRV demand history** — 24-hour history of `binary_sensor.*_heat_required`
  for all 11 TRVs — shows overlapping demand at a glance
- **Battery levels** — current battery % for all 11 TRVs

---

## Installation

### 1. HACS prerequisites

Install both from HACS → Frontend → search and install:
- **Mushroom** (by piitaya)
- **card-mod** (by Thomas Loven)

Hard refresh the browser after installing (`Ctrl+Shift+R`).

### 2. Automations

Settings → Automations → + Create automation → top right ⋮ → Edit as YAML

`boiler_automation.yaml` contains **two** automations separated by `---`.
Import each one separately:

1. Paste the first automation (Boiler ON) → Save
2. Create another automation → paste the second (Boiler OFF) → Save
3. Create another automation → paste the full contents of
   `heating_log_automation.yaml` → Save

### 3. Dashboard

Settings → Dashboards → Add dashboard:
- Title: `Heating`
- URL path: `heating`
- Icon: `mdi:radiator`
- Tick **Show in sidebar**

Open the new dashboard → Edit (pencil icon) → Raw configuration editor →
select all and replace with the contents of `heating_dashboard.yaml` → Save.

---

## How demand signalling works

```
TRV valve opens (local temp < target temp)
        ↓
hvac_action = "heating" on climate entity
        ↓
Boiler ON automation triggers immediately
        ↓
switch.boiler_switch turns ON
        ↓
ZBMINIR2 relay closes → 230V RT circuit closes → boiler fires

        ↓ (when TRV satisfied)

hvac_action leaves "heating"
        ↓
Boiler OFF automation triggers
        ↓ checks all TRVs — if any still heating, stop here
        ↓ waits 3 minutes
        ↓ re-checks — if demand returned or switch manually on, abort
switch.boiler_switch turns OFF
        ↓
ZBMINIR2 relay opens → boiler returns to standby
```

Multiple TRVs can demand heat simultaneously. Any single TRV demanding heat
keeps the boiler running — the boiler only turns off when **all** TRVs
are satisfied and have remained so for 3 minutes.

---

## Z2M configuration notes

- TRVs paired directly to Z2M — no Hive hub required
- ZBMINIR2 paired to Z2M — appears as `switch.boiler_switch` in HA
- Set ZBMINIR2 `power_on_behavior` to `off` in Z2M device settings so the
  relay starts in the safe (open) state after any power cut or reboot
- The living room group (`climate.hive_trv_group_living_room`) is created
  in Z2M Groups — add TV, Bay and Dining TRVs to it

---

## Troubleshooting

**Boiler turns on at startup**
The ZBMINIR2 `power_on_behavior` may be set to `previous` or `on`. Set it
to `off` in Z2M → Devices → ZBMINIR2 → Settings.

**TRV not demanding heat despite being below target**
Check `switch.hive_trv_*_heat_available` is `on`. If off, the TRV is in
summer mode and the valve will not open.

**Flame badge not showing**
Ensure both Mushroom Cards and card-mod are installed and the browser has
been hard refreshed after installation.

**Logbook entries not appearing**
Ensure the `heating_log_automation.yaml` automation is enabled and the HA
logbook integration is active (it is by default).
