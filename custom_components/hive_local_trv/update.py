"""Update platform for Hive Local TRV.

Registers a native HA update entity so new releases appear in
Settings → Updates (the yellow bell notification) alongside other
HA and HACS updates.

Checks the latest GitHub release tag against the installed manifest
version and marks the entity as having an update available when they differ.
"""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.update import (
    UpdateEntity,
    UpdateEntityFeature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import DOMAIN

_L = logging.getLogger(__name__)

GITHUB_RELEASES_URL = (
    "https://api.github.com/repos/gashwell/Hive-TRV-Local/releases/latest"
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Hive Local TRV update entity."""
    async_add_entities([HiveLocalTRVUpdateEntity(entry)], update_before_add=True)


class HiveLocalTRVUpdateEntity(UpdateEntity):
    """Update entity that tracks GitHub releases for Hive Local TRV."""

    _attr_has_entity_name       = True
    _attr_name                  = "Hive Local TRV"
    _attr_supported_features    = UpdateEntityFeature.RELEASE_NOTES
    _attr_title                 = "Hive Local TRV"
    _attr_device_info           = None  # integration-level, not device-level

    def __init__(self, entry: ConfigEntry) -> None:
        """Initialise."""
        self._entry             = entry
        self._attr_unique_id    = f"{entry.entry_id}_update"
        self._latest_version:  str | None = None
        self._release_notes:   str | None = None
        self._release_url:     str | None = None

    @property
    def installed_version(self) -> str | None:
        """Return the currently installed version from manifest.json."""
        try:
            from .manifest import async_get_custom_components  # type: ignore[import]
        except ImportError:
            pass
        # Read directly from the manifest bundled with this install
        import importlib.resources as pkg
        import json
        try:
            ref = pkg.files("custom_components.hive_local_trv").joinpath("manifest.json")
            with ref.open("r") as f:
                return json.load(f).get("version")
        except Exception:
            pass
        # Fallback: read from disk relative to this file
        import os, json as _json
        manifest_path = os.path.join(os.path.dirname(__file__), "manifest.json")
        try:
            with open(manifest_path) as f:
                return _json.load(f).get("version")
        except Exception:
            return None

    @property
    def latest_version(self) -> str | None:
        """Return the latest version available on GitHub."""
        return self._latest_version

    @property
    def release_notes(self) -> str | None:
        """Return release notes for the latest version."""
        return self._release_notes

    @property
    def release_url(self) -> str | None:
        """Return URL to the latest release."""
        return self._release_url

    async def async_update(self) -> None:
        """Fetch the latest release from GitHub."""
        try:
            session = async_get_clientsession(self.hass)
            async with session.get(
                GITHUB_RELEASES_URL,
                headers={"Accept": "application/vnd.github+json"},
                timeout=10,
            ) as resp:
                if resp.status != 200:
                    _L.debug("GitHub releases fetch returned %s", resp.status)
                    return
                data = await resp.json()

            tag = data.get("tag_name", "")
            # Strip leading 'v' so we compare e.g. "1.0.5" == "1.0.5"
            self._latest_version = tag.lstrip("v") if tag else None
            self._release_notes  = data.get("body")
            self._release_url    = data.get("html_url")

        except Exception as exc:
            _L.debug("Failed to fetch latest release from GitHub: %s", exc)
