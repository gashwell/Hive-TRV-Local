# Hive TRV Local — Architecture & Decision Guide

---

## Version overview

| | v1 | v2 | v4 (current) |
|---|---|---|---|
| **Repo** | `Hive-TRV-Local` | `Hive-TRV-Local-v2` | `Hive-TRV-Local-v3` |
| **Domain** | `hive_local_trv` | `hive_trv_local` | `hive_trv_local` |
| **Status** | Archived | Superseded | Active |
| **Device entries** | No — uses Z2M entities | No — uses Z2M entities | Yes — per TRV and receiver |
| **Entity suppression** | No | No | Yes — TRV hidden when grouped |
| **Receiver support** | No | No | Yes — SLR1/SLR2/OTR1 |
| **Group engine** | Custom | Custom | Custom (v2 engine) |
| **Boiler demand** | ✓ | ✓ | ✓ |
| **Schedules** | Custom slots | Custom slots | Custom slots |
| **Boost** | Group only | Group only | Per device + per group |
| **Cards** | ✓ auto | ✓ auto | ✓ auto |

---

## v4 architecture

```
You pair TRVs to Zigbee2MQTT as normal
        │
        ▼
Zigbee2MQTT publishes state to MQTT broker
        │
        ▼
Hive TRV Local — TRV entry (one per device)
  └── HiveDeviceCoordinator
        subscribes to: zigbee2mqtt/Living Room TRV
        parses: temperature, hvac_mode, battery, pi_heating_demand
        creates: climate.*, sensor.*, number.*
        │
        ▼ (when TRV added to a group)
        individual climate.* hidden in entity registry
        │
        ▼
Hive TRV Local — Groups entry (single instance)
  └── HiveRoomCoordinator (one per group)
        reads:    member current_temperature from hass.states
        commands: climate.set_temperature, climate.set_hvac_mode via HA services
        creates:  climate.* (group), button.* (boost), number.* (boost defaults)
        │
        ▼
  └── BoilerDemandManager
        watches:  hvac_action on all group member climate entities
        drives:   receiver climate / switch / input_boolean
```

### Data flow — temperature command

```
User adjusts target on group card
        │
        ▼
HiveRoomCoordinator.async_set_temperature()
        │
        ▼
climate.set_temperature service call
  entity_id: [climate.living_room_trv_1, climate.living_room_trv_2]
        │
        ▼
HA MQTT integration publishes to Z2M
        │
        ▼
Zigbee2MQTT sends to physical TRV over Zigbee
```

### Data flow — boiler demand

```
TRV state update: hvac_action = "heating"
        │
        ▼
BoilerDemandManager.async_evaluate()
  any member heating? → turn_on boiler entity
  no members heating? → turn_off boiler entity
```

### Entity suppression

```
User creates group with [climate.living_room_trv_1]
        │
        ▼
config_flow._suppress_member_entities(hide=True)
  entity_registry.async_update_entity(
      "climate.living_room_trv_1",
      hidden_by=RegistryEntryHider.INTEGRATION
  )
  → entity disappears from UI, still works for service calls
        │
        ▼
User removes TRV from group
        │
        ▼
config_flow._suppress_member_entities(hide=False)
  entity_registry.async_update_entity(
      "climate.living_room_trv_1",
      hidden_by=None
  )
  → entity immediately reappears, no restart
```

---

## Storage schema (v4)

```json
{
  "schema_version": 1,
  "rooms": {
    "<uuid>": {
      "name": "Living Room",
      "members": ["climate.living_room_trv_1", "climate.living_room_trv_2"],
      "temp_sensors": [],
      "schedule": [
        {"days": [0,1,2,3,4], "time": "06:30", "temperature": 21.0},
        {"days": [0,1,2,3,4], "time": "09:00", "temperature": 18.0}
      ],
      "boost_temperature": 22.0,
      "boost_duration": 30
    }
  }
}
```

Stored at: `/config/.storage/hive_trv_local.<groups_entry_id>`

---

## Config entry types

v4 uses three types of config entry under one domain:

| `entry_type` | Multi-instance | Platforms | Created by |
|---|---|---|---|
| `trv` | Yes | climate, sensor, number | Add a TRV |
| `receiver` | Yes | climate, sensor, button, number, select | Add a receiver |
| `groups` | No (one only) | climate, button, number | Set up room group manager |

All three share the domain `hive_trv_local`. The `entry_type` key in `entry.data`
distinguishes them. Each has its own options flow.

---

## Group entity attributes

The room group `climate.*` entity exposes:

| Attribute | Type | Description |
|---|---|---|
| `members` | list | Member entity IDs |
| `member_count` | int | Number of members |
| `member_temperatures` | dict | `{entity_id: temp}` per member |
| `heat_required` | bool | True if any member is heating |
| `mode` | str | `manual` / `schedule` / `boost` / `off` |
| `schedule` | list | Current schedule slots |
| `schedule_current_slot` | int | Index of active slot |
| `boost_ends` | datetime | When boost expires (boost mode only) |
| `boost_remaining_minutes` | int | Minutes remaining (boost mode only) |

---

## Cards

### Which card for which entity?

```
climate.* from hive_trv_local (entry_type=trv)
    → custom:hive-trv-card

climate.* from hive_trv_local (room group)
    → custom:hive-trv-group-card
```

Both cards are auto-registered. On HA 2026.6+, both implement `getEntitySuggestion`
and appear in the entity-based card picker.

### Distinguishing TRV from group entities

In Developer Tools → States, check attributes:
- Has `pi_heating_demand` or `battery` → individual TRV → `hive-trv-card`
- Has `members` array → room group → `hive-trv-group-card`

---

## Event bus

Room lifecycle events (fired on the HA event bus):

| Event | Payload | Purpose |
|---|---|---|
| `hive_trv_local_room_added` | `entry_id, room_id, coordinator` | Platforms register entities |
| `hive_trv_local_room_removed` | `entry_id, room_id, freed_members` | Platforms remove entities |
| `hive_trv_local_room_updated` | `entry_id, room_id, new_members` | Coordinator updates membership |

---

## Services

### Group services (domain: `hive_trv_local`)

| Service | Description |
|---|---|
| `group_boost` | Start timed boost on a room group |
| `group_end_boost` | Cancel active boost |
| `group_set_schedule` | Set custom weekly schedule |
| `group_clear_schedule` | Remove schedule (returns to manual) |
| `group_advance_schedule` | Skip to next slot immediately |

---

## Versioning scheme

```
MAJOR.MINOR.PATCH

Major:  Breaking change (new entry type structure, storage schema)
Minor:  New feature (new entity, new service, new card feature)
Patch:  Bug fix
```

---

## Upgrade path

```
v1 (hive_local_trv)
  └─► v2 (hive_trv_local) — different domain, can coexist with v1
        └─► v4 (hive_trv_local) — same domain as v2, delete v2 entries first
                                   add TRVs individually, then create groups
```

v1 and v2/v4 use **different HA domains** — they can coexist.  
v2 and v4 share the same domain — **delete all v2 entries before installing v4**.
