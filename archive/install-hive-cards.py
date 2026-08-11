#!/usr/bin/env python3
"""
Hive TRV Card Installer for Home Assistant
==========================================
Downloads hive-trv-card.js and hive-trv-group-card.js from GitHub,
places them in /config/www/, registers them as Lovelace resources,
and replaces any existing thermostat/tile/weather cards applied to
Hive/Danfoss TRV climate entities with the correct Hive TRV card.

Run on your HA server:
  python3 install-hive-cards.py

Tested on Home Assistant OS and Container installs.
"""

import json
import os
import shutil
import sys
import urllib.request
from pathlib import Path

# ── Config ─────────────────────────────────────────────────────────────────────

REPO_V2 = "gashwell/Hive-TRV-Local-v2"
REPO_V3 = "gashwell/Hive-TRV-Local-v3"

CARD_FILES = {
    "hive-trv-card.js":       "custom:hive-trv-card",
    "hive-trv-group-card.js": "custom:hive-trv-group-card",
}

# Lovelace card types that will be replaced when applied to Hive TRV entities
REPLACE_CARD_TYPES = {
    "thermostat",
    "tile",
    "entities",
    "entity",
    "humidifier",
    "climate",
}

# Attribute that distinguishes a room group climate entity from an individual TRV
GROUP_MARKER_ATTR = "members"

HA_CONFIG     = Path("/config")
WWW_DIR       = HA_CONFIG / "www"
STORAGE_DIR   = HA_CONFIG / ".storage"
def _find_lovelace():
    candidates = [STORAGE_DIR / n for n in (
        "lovelace", "lovelace.default_view", "lovelace_default_view", "frontend.lovelace",
    )]
    if STORAGE_DIR.exists():
        candidates += [f for f in STORAGE_DIR.iterdir()
                       if f.name.startswith("lovelace") and f not in candidates]
    return next((c for c in candidates if c.exists()), STORAGE_DIR / "lovelace")

LOVELACE_FILE = _find_lovelace()

# ── Helpers ────────────────────────────────────────────────────────────────────

def log(msg):       print(f"  {msg}")
def ok(msg):        print(f"  ✓  {msg}")
def warn(msg):      print(f"  ⚠  {msg}")
def err(msg):       print(f"  ✗  {msg}", file=sys.stderr)
def section(title): print(f"\n── {title} {'─'*(50-len(title))}")


def download_file(url: str, dest: Path) -> bool:
    try:
        urllib.request.urlretrieve(url, dest)
        ok(f"Downloaded {dest.name} ({dest.stat().st_size:,} bytes)")
        return True
    except Exception as e:
        err(f"Failed to download {url}: {e}")
        return False


def get_latest_release_asset_url(repo: str, filename: str) -> str:
    api_url = f"https://api.github.com/repos/{repo}/releases/latest"
    req = urllib.request.Request(api_url, headers={"Accept": "application/vnd.github+json"})
    with urllib.request.urlopen(req) as r:
        release = json.loads(r.read())
    tag = release["tag_name"]
    return (f"https://raw.githubusercontent.com/{repo}/{tag}"
            f"/custom_components/hive_trv_local/{filename}")


def load_lovelace() -> dict | None:
    if not LOVELACE_FILE.exists():
        warn(f"Lovelace storage not found at {LOVELACE_FILE}")
        warn("YAML-mode or storage-mode dashboard not found.")
    warn("Cards may already work if integration is running.")
    warn("Try: hard-refresh browser then Add Card > search Hive TRV")
    warn("Manual: Settings > Dashboards > Resources > Add:")
    warn("  /local/hive-trv-card.js  (JavaScript Module)")
    warn("  /local/hive-trv-group-card.js  (JavaScript Module)")
    return None
    try:
        return json.loads(LOVELACE_FILE.read_text())
    except Exception as e:
        err(f"Failed to read lovelace storage: {e}")
        return None


def save_lovelace(data: dict) -> bool:
    backup = LOVELACE_FILE.with_suffix(".bak")
    shutil.copy2(LOVELACE_FILE, backup)
    ok(f"Backup saved to {backup.name}")
    try:
        LOVELACE_FILE.write_text(json.dumps(data, indent=2))
        return True
    except Exception as e:
        err(f"Failed to write lovelace: {e}")
        shutil.copy2(backup, LOVELACE_FILE)
        err("Restored backup.")
        return False


def load_ha_states() -> dict:
    """Load entity states from HA storage to identify entity types."""
    states = {}
    states_file = STORAGE_DIR / "core.restore_state"
    if not states_file.exists():
        return states
    try:
        data = json.loads(states_file.read_text())
        for entry in data.get("data", []):
            state = entry.get("state", {})
            eid   = state.get("entity_id", "")
            attrs = state.get("attributes", {})
            if eid.startswith("climate."):
                states[eid] = attrs
    except Exception:
        pass
    return states


def is_group_entity(entity_id: str, states: dict) -> bool:
    """True if the climate entity is a Hive TRV group (has members attribute)."""
    attrs = states.get(entity_id, {})
    return isinstance(attrs.get(GROUP_MARKER_ATTR), list)


def card_for_entity(entity_id: str, states: dict) -> str:
    """Return the correct custom card type for a climate entity."""
    if is_group_entity(entity_id, states):
        return "custom:hive-trv-group-card"
    return "custom:hive-trv-card"


def find_climate_entities_in_dashboard(data: dict) -> list[dict]:
    """Walk all Lovelace cards and find ones with a Hive TRV climate entity."""
    found = []
    views = data.get("data", {}).get("config", {}).get("views", [])
    for vi, view in enumerate(views):
        for ci, card in enumerate(view.get("cards", [])):
            eid = card.get("entity", "")
            if eid.startswith("climate.") and card.get("type") in REPLACE_CARD_TYPES:
                found.append({"view_idx": vi, "card_idx": ci, "entity": eid, "card": card})
    return found


def replace_cards_in_dashboard(data: dict, replacements: list[dict]) -> dict:
    """Apply card replacements to the Lovelace data structure."""
    for r in replacements:
        views = data["data"]["config"]["views"]
        old   = views[r["view_idx"]]["cards"][r["card_idx"]]
        new   = {
            "type":   r["new_type"],
            "entity": r["entity"],
        }
        if r.get("name"):
            new["name"] = r["name"]
        views[r["view_idx"]]["cards"][r["card_idx"]] = new
        log(f"Replaced {old['type']} → {r['new_type']} for {r['entity']}")
    return data


def register_resources(data: dict, files: list[str]) -> dict:
    """Ensure Lovelace resource entries exist for the card JS files."""
    config  = data.get("data", {}).get("config", {})
    current = config.get("resources", [])
    existing_urls = {r.get("url", "") for r in current}

    added = []
    for fname in files:
        url = f"/local/{fname}"
        if url not in existing_urls:
            current.append({"url": url, "type": "module"})
            added.append(url)
            ok(f"Registered resource: {url}")
        else:
            log(f"Resource already registered: {url}")

    config["resources"] = current
    data["data"]["config"] = config
    return data


# ── Main ───────────────────────────────────────────────────────────────────────

def main():
    print("Hive TRV Card Installer")
    print("=" * 54)

    # Detect which repo to use
    domain_flag = STORAGE_DIR / "core.config_entries"
    repo = REPO_V2
    if domain_flag.exists():
        try:
            entries = json.loads(domain_flag.read_text())
            for entry in entries.get("data", {}).get("entries", []):
                if entry.get("domain") == "hive_trv_local":
                    version_hint = entry.get("version", 1)
                    # v3 uses helper_config_flow
                    repo = REPO_V3 if entry.get("source") == "helper" else REPO_V2
                    log(f"Detected hive_trv_local — using {repo}")
                    break
        except Exception:
            pass
    print(f"  Source repo: https://github.com/{repo}")

    # ── Step 1: Download card files ────────────────────────────────────────────
    section("Downloading card files")
    WWW_DIR.mkdir(parents=True, exist_ok=True)

    downloaded = []
    for fname in CARD_FILES:
        try:
            url  = get_latest_release_asset_url(repo, fname)
            dest = WWW_DIR / fname
            if download_file(url, dest):
                downloaded.append(fname)
        except Exception as e:
            err(f"Could not get URL for {fname}: {e}")
            # Fall back to main branch
            url  = f"https://raw.githubusercontent.com/{repo}/main/custom_components/hive_trv_local/{fname}"
            dest = WWW_DIR / fname
            if download_file(url, dest):
                downloaded.append(fname)

    if not downloaded:
        err("No card files downloaded — aborting.")
        sys.exit(1)

    # ── Step 2: Load state and Lovelace ───────────────────────────────────────
    section("Loading HA state")
    states    = load_ha_states()
    lovelace  = load_lovelace()

    if lovelace is None:
        section("Manual resource registration required")
        warn("Could not access Lovelace storage automatically.")
        print()
        print("  Add these resources manually in:")
        print("  Settings → Dashboards → ⋮ → Resources → Add")
        for fname in downloaded:
            print(f"    URL: /local/{fname}   Type: JavaScript Module")
        sys.exit(0)

    # ── Step 3: Register resources ─────────────────────────────────────────────
    section("Registering resources")
    lovelace = register_resources(lovelace, downloaded)

    # ── Step 4: Find and replace cards ────────────────────────────────────────
    section("Scanning dashboard cards")
    candidates = find_climate_entities_in_dashboard(lovelace)

    if not candidates:
        ok("No replaceable climate cards found in the default dashboard.")
        warn("Cards on custom dashboards or views stored in YAML files are not scanned.")
    else:
        print(f"  Found {len(candidates)} card(s) to review:\n")
        replacements = []
        for c in candidates:
            eid      = c["entity"]
            old_type = c["card"].get("type", "?")
            new_type = card_for_entity(eid, states)
            name     = c["card"].get("name")
            print(f"  entity : {eid}")
            print(f"  current: {old_type}")
            print(f"  replace: {new_type}")
            answer = input("  Replace? [Y/n]: ").strip().lower()
            if answer in ("", "y", "yes"):
                replacements.append({**c, "new_type": new_type, "name": name})
            print()

        if replacements:
            section("Applying replacements")
            lovelace = replace_cards_in_dashboard(lovelace, replacements)

    # ── Step 5: Save ──────────────────────────────────────────────────────────
    section("Saving changes")
    if save_lovelace(lovelace):
        ok("Lovelace storage updated.")
    else:
        sys.exit(1)

    # ── Done ──────────────────────────────────────────────────────────────────
    section("Done")
    ok("Card files in /config/www/")
    ok("Resources registered in Lovelace storage")
    print()
    print("  Next steps:")
    print("  1. Restart Home Assistant  (Settings → System → Restart)")
    print("  2. Hard-refresh your browser  (Ctrl+Shift+R / Cmd+Shift+R)")
    print("  3. Add cards to dashboards via  Edit → Add Card → search 'Hive TRV'")
    print()
    print("  Card YAML — individual TRV:")
    print("    type: custom:hive-trv-card")
    print("    entity: climate.your_trv_entity")
    print()
    print("  Card YAML — room group:")
    print("    type: custom:hive-trv-group-card")
    print("    entity: climate.your_room_group")


if __name__ == "__main__":
    main()
