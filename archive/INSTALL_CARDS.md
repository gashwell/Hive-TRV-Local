# Installing the Hive TRV Cards on your HA Server

The cards (`hive-trv-card` and `hive-trv-group-card`) are bundled with the
integration and auto-registered when it loads. If auto-registration fails, or
you want to apply them to existing dashboard cards, use the installer script.

---

## Quick start (recommended)

SSH into your HA server and run:

```bash
cd /config
curl -fsSL https://raw.githubusercontent.com/gashwell/Hive-TRV-Local-v2/main/install-hive-cards.py \
  | python3
```

Or for v3:
```bash
cd /config
curl -fsSL https://raw.githubusercontent.com/gashwell/Hive-TRV-Local-v3/main/install-hive-cards.py \
  | python3
```

Then restart Home Assistant and hard-refresh your browser.

---

## What the script does

1. **Downloads** `hive-trv-card.js` and `hive-trv-group-card.js` from the
   latest release into `/config/www/`

2. **Registers** both files as Lovelace JavaScript Module resources in
   `/config/.storage/lovelace`

3. **Scans** your default dashboard for existing `thermostat`, `tile`, or
   `entity` cards applied to `climate.*` entities

4. **Asks** for each one: replace with the correct Hive TRV card?
   - Z2M MQTT climate entities → `custom:hive-trv-card`
   - Hive TRV Local group entities → `custom:hive-trv-group-card`

5. **Backs up** the Lovelace storage before making changes

---

## Manual install (if SSH is not available)

1. Download both JS files from the latest release:
   - `hive-trv-card.js`
   - `hive-trv-group-card.js`

2. Copy to `/config/www/` using the HA File Editor add-on or Samba

3. Register resources:
   **Settings → Dashboards → ⋮ → Resources → Add**
   - URL: `/local/hive-trv-card.js`  Type: JavaScript Module
   - URL: `/local/hive-trv-group-card.js`  Type: JavaScript Module

4. Restart Home Assistant

5. Add cards via **Dashboard → Edit → Add Card → search "Hive TRV"**

---

## Adding cards manually

**Individual TRV** (Z2M entity, from MQTT integration):
```yaml
type: custom:hive-trv-card
entity: climate.living_room_trv
battery_entity: sensor.living_room_trv_battery
demand_entity: sensor.living_room_trv_pi_heating_demand
orientation_entity: select.living_room_trv_mounting_orientation
name: Living Room
```

**Room group** (Hive TRV Local group entity):
```yaml
type: custom:hive-trv-group-card
entity: climate.living_room
name: Living Room
```

---

## How to find your entity names

- **Settings → Entities** → search `climate.` → Integration column shows MQTT or Hive TRV Local
- MQTT entities = individual TRVs → use `hive-trv-card`
- Hive TRV Local entities = room groups → use `hive-trv-group-card`

---

## Troubleshooting

**Card not appearing in picker** — clear browser cache: Ctrl+Shift+R (Windows/Linux) or Cmd+Shift+R (Mac)

**"Custom element doesn't exist"** — the JS file is not loaded. Check:
- File exists at `/config/www/hive-trv-card.js`
- Resource is registered in Settings → Dashboards → Resources
- HA was restarted after file was placed

**Script fails to find lovelace** — if you use YAML-mode dashboards, the script
cannot auto-replace cards. Add them manually using the YAML above.
