# Changelog — Hive TRV Local

All notable changes. Newest first.

---

## v4.0.0 — 2026-08-10

Complete architecture rewrite.

### What's new

**Per-device config entries**

Each TRV and receiver is now added as a separate config entry with its own MQTT
subscription, coordinator, and entity set. This replaces all previous entity
detection attempts (device registry, state attribute scanning, platform filtering)
with a simple, reliable approach: you tell the integration the Z2M topic, and it
subscribes directly.

- Add a TRV → enter name + Z2M topic → creates `climate`, `sensor` (battery,
  heating demand), `number` (boost temp, boost duration, frost protection)
- Add a receiver → enter name + topic + model → creates `climate`, `sensor`
  (running state, boost remaining), `button` (boost heating, boost water for SLR2),
  `number` (boost temp, boost duration, frost temp, water boost duration for SLR2),
  `select` (water mode for SLR2)

**Entity suppression**

When a TRV is added to a room group its individual `climate.*` entity is hidden
automatically via the HA entity registry (`hidden_by = INTEGRATION`). The TRV is
controlled through the group. Remove it from the group and the entity is immediately
restored — no restart required.

**Receiver support**

Full SLR1, SLR2, and OTR1 support. SLR2 dual-channel (heating + hot water) with
separate water mode select, water boost button, and water boost remaining sensor.

**Member picker**

The room group member picker now shows only TRVs registered with this integration —
no entity detection, no guessing. Add your TRVs first, then create groups.

### What's the same

- Room groups, boiler demand, schedules, boost, storage — all from v2
- Both Lovelace cards auto-registered (`hive-trv-card`, `hive-trv-group-card`)
- HA 2026.6 card picker support (`getEntitySuggestion`)
- Smart reload (group changes don't restart HA)
- Full logging throughout

### Upgrade from v3.x / v2.x

1. Delete all existing Hive TRV Local integration entries
2. Update via HACS
3. Restart Home Assistant
4. Add Integration → Add a TRV (repeat for each TRV)
5. Add Integration → Add a receiver (if applicable)
6. Add Integration → Set up room group manager
7. Configure → Create room groups

---

## v3.1.3 — 2026-08-10

Multi-select entity picker for TRV members. Added `extra_topics` text field as fallback.

## v3.1.2 — 2026-08-10

Fix: CONFIG_VERSION mismatch caused Configure button to not appear.

## v3.1.1 — 2026-08-10

Remove stale files from previous v3 pre-release that prevented the integration loading.

## v3.1.0 — 2026-08-10

Clean-slate rewrite. Member selection via Z2M MQTT topics.

## v3.0.x — 2026-06-xx

Pre-release builds based on climate_group_helper (superseded).

---

## v2.0.12 — 2026-08-10

TRV detection: remove platform filter entirely, add manufacturer matching.

## v2.0.11 — 2026-08-10

TRV detection: switch to Z2M state attribute matching. Remove device registry.

## v2.0.10 — 2026-08-10

TRV detection: remove platform filter (was silently excluding all TRVs).

## v2.0.9 — 2026-08-10

TRV detection: substring model match, include no-model Z2M entities, log results.

## v2.0.8 — 2026-08-10

Fix add group failing (smart reload — group changes no longer trigger restart).
Add info/debug logging throughout `__init__.py`, `room.py`, `boiler.py`.

## v2.0.7 — 2026-08-10

Fix edit/delete group options missing from Configure menu.
Fix `DATA_BOILER` constant usage in settings step.

## v2.0.6 — 2026-08-10

Add `getEntitySuggestion` to both cards for HA 2026.6 entity-based card picker.

## v2.0.5 — 2026-08-10

Fix fragile service entity lookup (entity registry instead of slug matching).
Expose `boiler_entity` as public property on `BoilerDemandManager`.
Fix private `_boiler` access in `button.py`.

## v2.0.1–2.0.4 — 2026-06-03

Initial v2 releases — clean-room rewrite of v1. Core architecture: room groups,
boiler demand, schedules, boost, storage, event bus, two Lovelace cards, HACS compliance.
