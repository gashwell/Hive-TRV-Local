# File reference

Detailed documentation for every source file in `custom_components/hive_local_trv/`.

---

## `manifest.json`

Standard HA custom component manifest.

| Field | Value | Notes |
|---|---|---|
| `domain` | `hive_local_trv` | Must match the directory name |
| `iot_class` | `local_push` | State updates arrive via MQTT push, not polling |
| `dependencies` | `["mqtt"]` | Ensures the MQTT integration is loaded first |
| `config_flow` | `true` | Enables the UI setup flow |
| `version` | `2.0.0` | Used by HACS for update detection |

---

## `const.py`

Central constants file. **All string literals that appear in more than one file are defined here.** Importing from `const.py` rather than duplicating strings prevents typos and makes renaming straightforward.

### Key groups

**Config / options keys** — `CONF_Z2M_BASE_TOPIC`, `CONF_BOILER_ENTITY`, `CONF_PERSON_ENTITIES`. These are the dict keys used in `config_entry.data` and `config_entry.options`. Changing them would require a migration.

**hass.data keys** — `DATA_HUB`, `DATA_STORE`. Each config entry stores its hub and store under `hass.data[DOMAIN][entry_id][DATA_HUB/DATA_STORE]`. The `holiday_mgr` and `presence_mgr` keys are inline strings in `__init__.py` for simplicity since they're only used in one place.

**Z2M MQTT topic templates** — String templates with `{base}` and optionally `{name}` placeholders. Formatted with `.format()` at the point of use. Never hardcoded elsewhere.

**Mode constants** — `MODE_OFF`, `MODE_MANUAL`, `MODE_SCHEDULE`, `MODE_BOOST`, `MODE_AWAY`, `MODE_HOLIDAY`. The climate entity uses these as preset mode names (shown in the UI) and the coordinators use them internally. `ALL_MODES` is not currently used but included for completeness.

**Service and attribute names** — All service identifiers (`SERVICE_BOOST` etc.) and service call attribute keys (`ATTR_BOOST_TEMPERATURE` etc.) are defined here. This ensures the service registration in `__init__.py` and the translations in `translations/en.json` use the same strings.

**`SWEEP_INTERVAL_S`** — 30 seconds. The period between active device-list requests to Z2M. Can be increased to reduce MQTT traffic on stable networks.

**`SUPPORTED_TRV_MODELS`** — A set containing `"UK7004240"` and `"TRV001"`. The hub checks `definition.model` from Z2M's device list against this set. Adding a new model here is all that's needed to support it (assuming the Z2M expose schema is compatible).

---

## `config_flow.py`

Implements the HA UI setup wizard and options flow.

### `HiveLocalTRVConfigFlow`

A single-step setup flow. Displays a form with three fields: Z2M base topic, optional boiler entity (using HA's entity selector filtered to climate/switch/input_boolean), and optional person entities (multi-select, filtered to person domain).

On submission it:
1. Verifies MQTT is available by calling `mqtt.async_get_mqtt_data()`
2. Sets the unique ID to the base topic string to prevent duplicate entries for the same Z2M instance
3. Creates the config entry with `data = {CONF_Z2M_BASE_TOPIC, CONF_BOILER_ENTITY, CONF_PERSON_ENTITIES}`

**Why entity selectors?** The HA `selector.EntitySelector` renders as a searchable dropdown in the UI, filtered to the specified domains. This is far better UX than a plain text field for entity IDs.

### `HiveLocalTRVOptionsFlow`

Allows changing the boiler entity and person entities after initial setup. Triggered from Settings → Integrations → Configure.

On save, `_async_update_listener` in `__init__.py` detects the options change and reloads the config entry, picking up the new values.

---

## `__init__.py`

Integration entry point. Responsible for:

1. **Setup** (`async_setup_entry`) — instantiates and wires up all managers, forwards to platforms
2. **Teardown** (`async_unload_entry`) — unloads platforms, calls `async_unload()` on hub and presence manager
3. **Service registration** (`_register_services`) — registers all nine services against the `DOMAIN`
4. **Room group lifecycle** (`_create_room_coordinator`) — creates `HiveRoomCoordinator`, registers with hub, fires HA bus event for climate platform to create its entity

### Service resolution strategy

Services resolve a `climate` entity ID to either a `HiveTRVCoordinator` or `HiveRoomCoordinator` by iterating `hass.data[DOMAIN]` and matching entity ID conventions:

- TRVs: `climate.{friendly_name_lowercased_underscored}`
- Rooms: `climate.{room_name_lowercased_underscored}_room`

This is a pragmatic lookup. A more robust approach would maintain a reverse index but this covers all practical cases without complexity.

### Service schemas

Service schemas use `voluptuous` and are defined at module level. They validate input types and ranges before handlers are called. Notable validations:

- `duration` is `vol.All(int, vol.Range(min=1, max=1440))` — minimum 1 minute, maximum 24 hours
- `days` in schedule slots are `[vol.All(int, vol.Range(min=0, max=6))]` — Monday to Sunday only
- `departure` and `return` are plain strings parsed with `datetime.fromisoformat()` in the handler, allowing both naive and timezone-aware datetimes

### Why services not actions?

HA 2024.x introduced "actions" as an alias for services. This integration uses the `services` terminology for compatibility with 2024.1+.

---

## `coordinator.py`

Contains two classes: `HiveTRVCoordinator` and `HiveTRVHub`.

### `HiveTRVCoordinator`

Extends `DataUpdateCoordinator` to get the listener/callback pattern for free. There is **no periodic polling** — `async_update()` is never called. All updates come from MQTT via `async_set_updated_data()`.

**Mode state machine fields:**

| Field | Type | Description |
|---|---|---|
| `_mode` | str | Current mode (one of the MODE_* constants) |
| `_manual_setpoint` | float | The setpoint to use in manual mode |
| `_pre_boost_mode` | str | Mode to restore when boost expires |
| `_pre_boost_setpoint` | float | Setpoint to restore when boost expires |
| `_boost_end` | datetime \| None | UTC datetime when boost expires |
| `_boost_task` | asyncio.Task \| None | The running boost timer coroutine |
| `_schedule_mgr` | ScheduleManager \| None | Attached by `set_schedule` service |

**`async_set_mode(mode, setpoint=None)`** — The central mode transition method. Cancels any running boost task, updates `_mode`, and pushes the appropriate setpoint to Z2M. Calls `async_write_ha_state_for_all()` to refresh all entities.

**`async_set_manual_temperature(temp)`** — Called when the user moves the temperature slider. Updates `_manual_setpoint` and pushes to Z2M. If currently in `off` mode, implicitly switches to `manual`.

**`async_start_boost(temperature, duration_minutes)`** — Saves current mode/setpoint, switches to `MODE_BOOST`, pushes boost temperature, starts an `asyncio.Task` timer. When the timer fires it calls `_boost_timer()` which calls `async_set_mode(_pre_boost_mode, _pre_boost_setpoint)`.

**`async_write_ha_state_for_all()`** — Triggers a state refresh across all entities listening to this coordinator by calling `async_set_updated_data(dict(self.data))` with the same data. This is a workaround for mode changes that don't involve a Z2M payload — the coordinator data hasn't changed but the HA state has (e.g. mode switched from manual to boost).

**Publish helpers** — `async_publish(payload)` sends to `{base}/{name}/set`. All higher-level helpers call this. The pattern makes the MQTT topic management entirely internal.

### `HiveTRVHub`

Singleton per config entry. Responsibilities:

1. **Discovery** — subscribes to two Z2M topics, reconciles device list against `SUPPORTED_TRV_MODELS`, creates/destroys coordinators
2. **Boiler demand** — attaches a listener to every coordinator; when `heat_required` changes on any TRV it calls `async_evaluate_boiler_demand()`
3. **heat_available broadcast** — tracks boiler entity state changes, broadcasts `heat_available` to all TRVs
4. **Platform registration** — platforms call `register_add_entities(platform, add_cb, remove_cb)` once. Hub calls `add_cb(coordinator)` for every existing TRV and for every new TRV discovered. Hub calls `remove_cb(friendly_name)` when a TRV disappears

**`_reconcile(devices)`** — Set arithmetic: computes `incoming - current` (new TRVs) and `current - incoming` (removed TRVs). Uses `hass.async_create_task()` rather than `await` to avoid blocking the MQTT callback.

**`_call_boiler(on)`** — Handles the domain differences between climate, switch, and input_boolean entities. For climate entities it uses `set_hvac_mode`; for others it uses `turn_on`/`turn_off`.

---

## `storage.py`

Wraps HA's `helpers.storage.Store` (which writes to `.storage/hive_local_trv_{entry_id}`) with typed accessors.

**Schema version** is set to `1`. If the schema changes in a future version, a migration function should be added.

**`async_load()`** — Called once at startup. If no stored data exists, initialises `self._data = {"trvs": {}, "rooms": {}}`.

**TRV helpers** — `get_trv_schedule`, `async_set_trv_schedule`, `async_set_trv_boost_defaults`, `get_trv_boost_temperature`, `get_trv_boost_duration`. All keyed on Z2M `friendly_name`.

**Room helpers** — `get_all_rooms`, `get_room`, `async_save_room`, `async_remove_room`, `async_set_room_schedule`. Rooms are keyed on a UUID generated at creation time (`str(uuid.uuid4())`).

**Holiday helpers** — `get_holiday`, `async_save_holiday`, `async_clear_holiday`. The holiday record includes `departure`, `return`, `active` flag, and `saved_modes` dict mapping friendly names to their pre-holiday modes.

---

## `schedule.py`

Implements weekly schedule management. Works identically for both individual TRVs and room groups.

### `ScheduleManager`

**Constructor** takes `hass`, a `name` (for logging), and `apply_fn` — an `async` callable that takes a temperature float and applies it to the target. This makes the class target-agnostic: the same code drives both a single TRV (`coordinator.async_set_temperature`) and a room group (`room_coord._apply_temperature`).

**`async_set_schedule(schedule)`** — Stores the slots, applies the currently-active slot immediately (so the temperature is correct if HA was restarted), then arms the timer for the next transition.

**`_active_slot()`** — Finds which slot is currently active. Logic:
1. Find all slots for today with `time ≤ now_time` → take the latest one
2. If none found for today before now, look for yesterday's last slot (handles midnight–first-slot-of-day gap)
3. Returns `None` if no slot found at all

**`_next_transition()`** — Searches forward up to 7 days to find the next future transition. Returns `(utc_datetime, temperature)`. The 7-day search handles sparse schedules (e.g. a schedule with only weekend slots).

**`advance_to_next()`** — Cancels the pending timer, applies the next slot's temperature immediately, then finds the slot after that and re-arms the timer. Returns `False` if there is no next slot.

**`callback_wrapper(coro_fn)`** — A module-level utility that wraps an async function into an HA `@callback`-compatible function (required by `async_track_point_in_time` which expects a synchronous callback). The wrapper calls `asyncio.ensure_future()` to schedule the coroutine.

---

## `holiday.py`

Implements date-range holiday mode.

### `HolidayManager`

**`async_setup()`** — Called at HA startup. Reads stored holiday state from `HiveTRVStore.get_holiday()` and re-arms any pending timers:
- If `return` has already passed → calls `_deactivate()` to clean up
- If holiday is currently active → re-arms the return timer only
- If departure is in the future → re-arms both timers

This ensures holiday mode survives HA restarts correctly.

**`async_set_holiday(departure_dt, return_dt)`** — Cancels any existing holiday, saves to store, then either activates immediately (if `departure ≤ now`) or arms a departure timer.

**`_activate(ret)`** — Iterates all TRV coordinators and room coordinators. For each: saves `coord.mode` into the `saved_modes` dict, sets `coord._mode = MODE_HOLIDAY`, publishes `DEFAULT_FROST_TEMP` to Z2M, calls `async_write_ha_state_for_all()`. Then saves the updated holiday record with `active: True` and arms the return timer.

**`_deactivate()`** — Reads `saved_modes` from the stored holiday record. For each coordinator: calls `async_set_mode(restore_mode)`. Clears the holiday record from storage.

**Priority** — Holiday mode sets `_mode` directly on coordinators, bypassing the normal `async_set_mode()` path. This means presence changes (which check `coord.mode`) see `MODE_HOLIDAY` and decline to interfere.

---

## `presence.py`

Implements geofencing via HA person entities.

### `PresenceManager`

**`async_setup()`** — If `person_entity_ids` is empty, returns immediately (no-op). Otherwise subscribes to state changes on all person entities, and evaluates initial state immediately at startup (so if HA restarts while everyone is away, away mode is re-activated correctly).

**`anyone_home`** — Checks if any tracked person's state is in `_HOME_STATES = {"home"}`. Only `"home"` counts as home; any other state (`"not_home"`, zone names like `"work"`, `"gym"`) is treated as away.

**`_evaluate()`** — Called on every person state change. If holiday is active (checked via `self._holiday_mgr.is_active`), returns immediately without action. Otherwise calls `_go_away()` or `_come_home()` as appropriate.

**`_go_away()`** — Sets `_away_active = True`, saves all modes to `_saved_modes` (keyed by friendly_name for TRVs and `__room__{room_id}` for room groups), sets `_mode = MODE_AWAY` directly on each coordinator, publishes frost protection temperature.

**`_come_home()`** — Sets `_away_active = False`. For each coordinator, reads the saved mode from `_saved_modes` and calls `async_set_mode(restore)`. Clears `_saved_modes`.

**Note on persistence** — Unlike holiday mode, away mode state is **not** persisted to storage. If HA restarts while everyone is away, `async_setup()` re-evaluates presence state immediately and re-activates away mode if needed. This is simpler and equally correct.

---

## `room.py`

### `HiveRoomCoordinator`

Extends `DataUpdateCoordinator`. Like `HiveTRVCoordinator`, it has no periodic polling — all updates are triggered by member TRV updates and temperature sensor state changes.

**`current_temperature`** — Collects temperatures from all sources (external sensors + TRV local sensors) into a single list, returns the average rounded to 1dp. Any source that is unavailable or unparseable is silently excluded. Returns `None` only if no valid source exists.

**`_apply_temperature(temp)`** — Fan-out: calls `coord.async_set_temperature(temp)` for every member TRV. Uses `self._get_coord(name)` which calls back into the hub to get the live coordinator — this handles the case where a TRV is discovered after the room group is created.

**`async_set_schedule(schedule)`** — Delegates to `self._schedule_mgr.async_set_schedule()`. The `ScheduleManager` is created in the room's `__init__` with `apply_fn = lambda temp: self._apply_temperature(temp)`, so schedule events fan out to all member TRVs.

**Room-level boost** — Identical pattern to TRV boost: saves modes/setpoints, pushes boost temp to all TRVs, arms asyncio timer, restores on expiry.

**`_refresh_data()`** — Assembles a summary dict and calls `async_set_updated_data()`. This triggers the CoordinatorEntity listener pattern on the room climate entity.

**`_NullCoord`** — A minimal stub returned by `_get_coord` when a named TRV hasn't been discovered yet. Has `heat_required = False` and `local_temperature = None`. Prevents `AttributeError` during startup when room groups are restored before their member TRVs are discovered.

---

## `entity.py`

### `HiveTRVEntity`

Base class for all per-TRV entities (except the room climate entity which uses `CoordinatorEntity` directly).

Sets `_attr_has_entity_name = True` so entity names are composed as "Device Name — Entity Name" in the UI.

**`device_info`** — Uses `DeviceInfo` with `identifiers={(DOMAIN, ieee_address)}`. All entities for the same TRV share the same `ieee_address`-based identifier, causing HA to group them under a single device.

`sw_version` is populated from `coordinator.device_info.get("software_build_id")` — Z2M provides this for devices that report it over OTA queries.

---

## `climate.py`

### `HiveTRVClimate`

Maps the coordinator mode state machine to HA's climate entity model:

| HA concept | Implementation |
|---|---|
| `hvac_mode = heat` | any mode except `off`, `away`, `holiday` |
| `hvac_mode = off` | `MODE_OFF`, `MODE_AWAY`, `MODE_HOLIDAY` |
| `hvac_action = heating` | `running_state == "heat"` from Z2M |
| `hvac_action = idle` | heat mode but not actively heating |
| `hvac_action = off` | hvac_mode is off |
| `preset_mode` | current mode (none if off/holiday) |

**`extra_state_attributes`** — Exposes additional diagnostic data: `pi_heating_demand`, `heat_required`, `battery`, `window_open`, `running_state`. In boost mode also exposes `boost_ends` and `boost_remaining_minutes`. In away/holiday mode exposes a boolean flag.

**`async_set_temperature`** — Calls `coordinator.async_set_manual_temperature()` which implicitly switches to manual mode if currently off.

### `HiveRoomClimate`

Extends `CoordinatorEntity[HiveRoomCoordinator]` directly (not `HiveTRVEntity`, since it's not a single device).

Uses a separate `DeviceInfo` with `identifiers={(DOMAIN, f"room_{coordinator.room_id}")}`, giving each room group its own device in HA.

**Dynamic registration** — Room climate entities are not created at platform setup time. Instead `async_setup_entry` registers listeners on the HA bus for `{DOMAIN}_room_added` and `{DOMAIN}_room_removed` events. When `__init__.py` fires these events (either at startup when restoring rooms from storage, or when `add_room` service is called), the climate platform creates/removes the entity. This allows rooms to be created and destroyed without reloading the entire integration.

---

## `sensor.py`

Two sensors per TRV:

**`HiveBatterySensor`** — `SensorDeviceClass.BATTERY`, `PERCENTAGE` unit, `MEASUREMENT` state class. Reads `coordinator.battery` which returns `int(data.get("battery"))`.

**`HiveDemandSensor`** — No device class (there's no standard device class for PI heating demand). Uses `MEASUREMENT` state class and `mdi:radiator` icon. Reads `coordinator.pi_heating_demand`.

Both use the same dynamic add/remove pattern as climate — the hub calls the registered `_add` / `_remove` callbacks.

---

## `button.py`

Two buttons per TRV:

**`HiveAdaptationButton`** — Sends `{"adaptation_run_control": "initiate_adaptation"}` to Z2M. The TRV runs a 5-minute calibration routine, learning the valve spring force and travel distance for its specific radiator. Should be run once after each physical installation.

**`HiveMountingButton`** — Sends `{"mounted_mode_control": true}` (inverted: `async_set_mounted(False)` → `mounted_mode_control: true` = enter mounting mode). Used if a TRV needs to be re-fitted to a different valve without factory resetting.

---

## `number.py`

Four number entities per TRV:

**`HiveOffsetNumber`** — Range ±2.5°C, step 0.1°C. Sends `regulation_setpoint_offset` to Z2M. Use this to compensate if a TRV consistently over or undershoots the target temperature. Reads current value back from `coordinator.get("regulation_setpoint_offset")`.

**`HiveAlgorithmScaleNumber`** — Range 1–10, integer steps, slider mode. Sends `algorithm_scale_factor`. Controls PID aggressiveness. Higher values = faster response but risk overshoot oscillation. Hidden by default (`_attr_entity_registry_enabled_default = False`) — only show if you're experiencing temperature oscillation.

**`HiveBoostTempNumber`** — Range 10–32°C, step 0.5°C. Reads/writes from `HiveTRVStore` (not Z2M — this is a stored default, not a live TRV attribute). Used by `async_start_boost()` when no explicit temperature is provided.

**`HiveBoostDurationNumber`** — Range 5–1440 minutes (5 min to 24 hours), step 5 minutes. Also stored in `HiveTRVStore`. Used as default boost duration.

---

## `select.py`

One select per TRV:

**`HiveKeypadLockoutSelect`** — Options: `unlock`, `lock1`, `lock2`. Sends `keypad_lockout` to Z2M. `lock1` prevents physical button presses. `lock2` is a stricter mode (implementation-defined by TRV firmware). Useful for child-proofing or preventing tampering in commercial settings.

Note: **programming mode** (setpoint / schedule / eco) was a select in earlier versions but was removed. The integration always sets TRVs to `setpoint` mode (HA is in control), and this is enforced in `HiveTRVCoordinator.async_setup()`.

---

## `translations/en.json`

Provides UI strings for:
- Config flow form labels and descriptions
- Options flow form labels
- Service names, descriptions, and field descriptions (shown in Developer Tools → Services)

Service translations use the `services` key introduced in HA 2024.x. Without these, services still work but show generic names in the UI.

---
