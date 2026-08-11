# Architecture

## Component overview

```
Home Assistant
│
├── config entry (one per Z2M instance)
│   ├── HiveTRVHub          — discovery + boiler demand
│   ├── HiveTRVStore        — persistent storage (.storage)
│   ├── HolidayManager      — date-range holiday mode
│   └── PresenceManager     — geofencing via person entities
│
├── per-TRV
│   ├── HiveTRVCoordinator  — MQTT state + mode state machine
│   └── ScheduleManager     — weekly schedule (attached on set_schedule)
│
└── per-room-group
    ├── HiveRoomCoordinator — aggregates N TRVs + M sensors
    └── ScheduleManager     — room-level schedule
```

## Data flow — TRV state update

```
Z2M (Zigbee radio)
    │ MQTT publish to zigbee2mqtt/{friendly_name}
    ▼
HiveTRVCoordinator._on_state()
    │ merges payload into self.data dict
    │ calls async_set_updated_data()
    ▼
DataUpdateCoordinator listeners fire
    │
    ├── Climate entity → writes HA state
    ├── Sensor entities → writes HA state
    └── Hub.async_evaluate_boiler_demand()
            │ any heat_required? → turn boiler on/off
            ▼
        mqtt.async_publish to boiler entity
```

## Data flow — discovery

```
Z2M bridge/devices topic (event-driven)
    OR
30-second sweep → bridge/request/devices → bridge/response/devices
    │
    ▼
HiveTRVHub._reconcile(device_list)
    │ filter by definition.model in SUPPORTED_TRV_MODELS
    │
    ├── New TRVs → _add_trv()
    │       creates HiveTRVCoordinator
    │       subscribes to MQTT state topic
    │       notifies all registered platform add_callbacks
    │
    └── Removed TRVs → _remove_trv()
            unsubscribes MQTT
            notifies all registered platform remove_callbacks
            entity.async_remove() called per entity
```

## Data flow — mode change

```
User (HA UI / automation / service)
    │ set_preset_mode("boost")
    ▼
HiveTRVClimate.async_set_preset_mode()
    │
    ▼
HiveTRVCoordinator.async_set_mode("boost")
    │
    ▼
HiveTRVCoordinator.async_start_boost()
    │ saves _pre_boost_mode, _pre_boost_setpoint
    │ publishes occupied_heating_setpoint to Z2M
    │ starts asyncio timer task
    │ calls async_write_ha_state_for_all()
    ▼
After duration expires:
HiveTRVCoordinator._boost_timer()
    │
    ▼
async_set_mode(_pre_boost_mode, _pre_boost_setpoint)
```

## Data flow — schedule

```
set_schedule service call
    │
    ▼
ScheduleManager.async_set_schedule(slots)
    │ _apply_current_slot() → pushes active temperature now
    │ _schedule_next_transition() → async_track_point_in_time
    │
    ▼
At transition time:
ScheduleManager._fire()
    │ apply_fn(temperature) → HiveTRVCoordinator.async_set_temperature()
    │ _schedule_next_transition() for the following slot
    ▼
mqtt.async_publish occupied_heating_setpoint → Z2M → TRV
```

## Data flow — boiler demand

```
HiveTRVCoordinator receives state update
    │ heat_required changes
    │
    ▼
coordinator.async_add_listener fires
    │
    ▼
HiveTRVHub.async_evaluate_boiler_demand()
    │ any_heat_required() checks all coordinators + room coordinators
    │
    ├── True + boiler currently off → _call_boiler(True)
    └── False + boiler currently on → _call_boiler(False)
            │
            ▼
        hass.services.async_call(domain, "turn_on"/"turn_off")
            OR
        climate.set_hvac_mode(heat/off)

Simultaneously:
HiveTRVHub._on_boiler_state_change()
    │ boiler entity state changes
    ▼
async_broadcast_heat_available(True/False)
    │
    ▼
All coordinators → mqtt.publish heat_available
```

## Priority hierarchy

When multiple mode managers are active, this priority order applies:

```
Holiday mode (highest)
    ↓ if not active
Away mode (geofencing)
    ↓ if not active
Boost mode
    ↓ if not active
Schedule / Manual / Off (normal operation)
```

Holiday mode prevents away mode from interfering. Away mode saves and restores modes (not temperatures). Both save/restore state independently.

## Storage schema

Stored at `.storage/hive_local_trv_{entry_id}`:

```json
{
  "trvs": {
    "lounge_trv": {
      "schedule": [
        {"days": [0,1,2,3,4], "time": "06:30", "temperature": 20.5}
      ],
      "boost_temperature": 22.0,
      "boost_duration": 30
    }
  },
  "rooms": {
    "uuid-room-id": {
      "name": "Living Room",
      "trvs": ["lounge_trv_1", "lounge_trv_2"],
      "temp_sensors": ["sensor.lounge_aqara_temperature"],
      "schedule": [],
      "boost_temperature": 22.0,
      "boost_duration": 30
    }
  },
  "holiday": {
    "departure": "2025-08-01T09:00:00+00:00",
    "return": "2025-08-14T18:00:00+00:00",
    "active": true,
    "saved_modes": {
      "lounge_trv": "schedule",
      "__room__uuid-room-id": "manual"
    }
  }
}
```

## MQTT topics used

| Topic | Direction | Purpose |
|---|---|---|
| `{base}/bridge/devices` | Subscribe | Event-driven device list from Z2M |
| `{base}/bridge/request/devices` | Publish | Request device list (30s sweep) |
| `{base}/bridge/response/devices` | Subscribe | Response to device list request |
| `{base}/{friendly_name}` | Subscribe | TRV state updates |
| `{base}/{friendly_name}/set` | Publish | Set TRV attributes |
