"""Boiler demand manager.

Watches hvac_action on all group member climate entities.
If any member is heating, the boiler/receiver entity is turned on.
When none are heating, it is turned off.
"""
from __future__ import annotations

import logging
from collections.abc import Callable
from typing import TYPE_CHECKING, Any

from homeassistant.components.climate import HVACAction
from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.event import async_track_state_change_event

if TYPE_CHECKING:
    from .room import HiveRoomCoordinator

_LOGGER = logging.getLogger(__name__)


class BoilerDemandManager:
    """Drives a boiler/receiver entity based on aggregate group heat demand.

    Watches the hvac_action attribute on all Z2M climate entities that are
    members of any room group. Turns the boiler on when any member is
    actively heating; turns it off when none are.
    """

    def __init__(
        self,
        hass: HomeAssistant,
        boiler_entity: str | None,
        get_rooms: Callable[[], dict[str, "HiveRoomCoordinator"]],
    ) -> None:
        self._hass         = hass
        self._boiler       = boiler_entity
        self._get_rooms    = get_rooms
        self._demand       = False
        self._unsubscribers: list[Callable] = []

    # ── Public API ─────────────────────────────────────────────────────────────

    @property
    def boiler_entity(self) -> str | None:
        """Return the configured boiler/receiver entity ID."""
        return self._boiler

    # ── Lifecycle ──────────────────────────────────────────────────────────────

    def update_boiler_entity(self, entity_id: str | None) -> None:
        """Update the boiler entity (called when options change)."""
        self._boiler = entity_id

    def subscribe_members(self, member_entity_ids: list[str]) -> None:
        """Subscribe to state changes for a set of member entity IDs."""
        if not member_entity_ids:
            return
        _LOGGER.debug("Boiler: subscribing to %d member(s): %s", len(member_entity_ids), member_entity_ids)
        self._unsubscribers.append(
            async_track_state_change_event(
                self._hass, member_entity_ids, self._on_state_change
            )
        )

    def unsubscribe_all(self) -> None:
        for unsub in self._unsubscribers:
            unsub()
        self._unsubscribers.clear()

    # ── Demand evaluation ──────────────────────────────────────────────────────

    @property
    def any_heat_required(self) -> bool:
        """True if any group member is actively calling for heat."""
        for room in self._get_rooms().values():
            if room.heat_required:
                return True
        return False

    async def async_evaluate(self) -> None:
        """Evaluate demand and drive boiler if state has changed."""
        if not self._boiler:
            return
        needed = self.any_heat_required
        if needed == self._demand:
            return
        self._demand = needed
        domain  = self._boiler.split(".")[0]
        service = "turn_on" if needed else "turn_off"
        try:
            await self._hass.services.async_call(
                domain, service,
                {ATTR_ENTITY_ID: self._boiler},
                blocking=False,
            )
            _LOGGER.info("Boiler demand → %s (%s)", "ON" if needed else "OFF", self._boiler)
        except Exception as exc:
            _LOGGER.warning("Boiler call failed: %s", exc)

    @callback
    def _on_state_change(self, _event: Any) -> None:
        self._hass.async_create_task(self.async_evaluate())

