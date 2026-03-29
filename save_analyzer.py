#!/usr/bin/env python3
"""
save_analyzer.py — Python bridge for parsing Dyson Sphere Program save files.

Accepts a .dsv file path as a command line argument, parses it using
dsp_save_parser (if available), extracts game state data, generates
recommendations, and outputs JSON to stdout.

Always outputs valid JSON, even on errors.
"""

import json
import os
import signal
import sys
import traceback

# Add the bundled dsp_save_parser_lib to the import path
_lib_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "dsp_save_parser_lib")
if os.path.isdir(_lib_dir) and _lib_dir not in sys.path:
    sys.path.insert(0, _lib_dir)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

TIMEOUT_SECONDS = 60  # hard cap so we never hang
MAX_FILE_SIZE_MB = 500  # refuse files larger than this

# DSP tech tree reference (subset — IDs match the game's internal numbering)
TECH_TREE = {
    # Science matrices
    1001: {"name": "Electromagnetic Matrix", "tier": 1, "category": "matrix"},
    1002: {"name": "Energy Matrix", "tier": 2, "category": "matrix"},
    1003: {"name": "Structure Matrix", "tier": 3, "category": "matrix"},
    1004: {"name": "Information Matrix", "tier": 4, "category": "matrix"},
    1005: {"name": "Gravity Matrix", "tier": 5, "category": "matrix"},
    1006: {"name": "Universe Matrix", "tier": 6, "category": "matrix"},

    # Logistics
    1101: {"name": "Basic Logistics System", "tier": 1, "category": "logistics"},
    1102: {"name": "Improved Logistics System", "tier": 2, "category": "logistics"},
    1103: {"name": "High Efficiency Logistics System", "tier": 3, "category": "logistics"},
    1104: {"name": "Planetary Logistics System", "tier": 2, "category": "logistics"},
    1105: {"name": "Interstellar Logistics System", "tier": 3, "category": "logistics"},

    # Smelter upgrades
    1201: {"name": "Smelting Purification", "tier": 1, "category": "smelter"},
    1202: {"name": "Plane Smelter", "tier": 3, "category": "smelter"},
    1203: {"name": "Negentropy Smelter", "tier": 4, "category": "smelter"},

    # Assembler upgrades
    1301: {"name": "Assembler Mk.I", "tier": 1, "category": "assembler"},
    1302: {"name": "Assembler Mk.II", "tier": 2, "category": "assembler"},
    1303: {"name": "Assembler Mk.III", "tier": 3, "category": "assembler"},
    1304: {"name": "Re-composing Assembler", "tier": 4, "category": "assembler"},

    # Belt speed
    1401: {"name": "Belt Mk.I", "tier": 1, "category": "belt"},
    1402: {"name": "Belt Mk.II", "tier": 2, "category": "belt"},
    1403: {"name": "Belt Mk.III", "tier": 3, "category": "belt"},

    # Power
    1501: {"name": "Thermal Power", "tier": 1, "category": "power"},
    1502: {"name": "Solar Energy", "tier": 1, "category": "power"},
    1503: {"name": "Wind Energy", "tier": 1, "category": "power"},
    1504: {"name": "Geothermal Energy", "tier": 2, "category": "power"},
    1505: {"name": "Mini Fusion Power Station", "tier": 3, "category": "power"},
    1506: {"name": "Artificial Star", "tier": 5, "category": "power"},

    # Dyson Sphere
    1601: {"name": "Dyson Sphere Stress System", "tier": 4, "category": "dyson"},
    1602: {"name": "Dyson Sphere Framework", "tier": 4, "category": "dyson"},
    1603: {"name": "Dyson Sphere Completion", "tier": 5, "category": "dyson"},

    # Mining
    1701: {"name": "Mining Efficiency I", "tier": 1, "category": "mining"},
    1702: {"name": "Mining Efficiency II", "tier": 2, "category": "mining"},
    1703: {"name": "Mining Efficiency III", "tier": 3, "category": "mining"},

    # Chemistry
    1801: {"name": "Basic Chemical Engineering", "tier": 1, "category": "chemistry"},
    1802: {"name": "Polymer Chemistry", "tier": 2, "category": "chemistry"},
    1803: {"name": "Advanced Chemical Engineering", "tier": 3, "category": "chemistry"},

    # Drones / Bots
    1901: {"name": "Construction Drone", "tier": 2, "category": "drone"},
    1902: {"name": "Drone Engine", "tier": 2, "category": "drone"},
    1903: {"name": "Drone Speed I", "tier": 3, "category": "drone"},

    # Research speed
    2001: {"name": "Research Speed I", "tier": 1, "category": "research"},
    2002: {"name": "Research Speed II", "tier": 2, "category": "research"},
    2003: {"name": "Research Speed III", "tier": 3, "category": "research"},
    2004: {"name": "Research Speed IV", "tier": 4, "category": "research"},
}

# Progression milestones used for recommendations
AUTOMATION_MILESTONES = [
    {"resource": "Iron Ingot", "priority": 1, "unlocked_by": None},
    {"resource": "Copper Ingot", "priority": 2, "unlocked_by": None},
    {"resource": "Magnetic Coil", "priority": 3, "unlocked_by": None},
    {"resource": "Circuit Board", "priority": 4, "unlocked_by": None},
    {"resource": "Electromagnetic Matrix", "priority": 5, "unlocked_by": 1001},
    {"resource": "Energetic Graphite", "priority": 6, "unlocked_by": None},
    {"resource": "Hydrogen", "priority": 7, "unlocked_by": None},
    {"resource": "Energy Matrix", "priority": 8, "unlocked_by": 1002},
    {"resource": "Diamond", "priority": 9, "unlocked_by": None},
    {"resource": "Titanium Ingot", "priority": 10, "unlocked_by": None},
    {"resource": "Structure Matrix", "priority": 11, "unlocked_by": 1003},
    {"resource": "Processor", "priority": 12, "unlocked_by": None},
    {"resource": "Information Matrix", "priority": 13, "unlocked_by": 1004},
    {"resource": "Graviton Lens", "priority": 14, "unlocked_by": 1005},
    {"resource": "Gravity Matrix", "priority": 15, "unlocked_by": 1005},
    {"resource": "Universe Matrix", "priority": 16, "unlocked_by": 1006},
]

BUILDING_PRIORITY = [
    "Smelter",
    "Assembler Mk.I",
    "Mining Machine",
    "Wind Turbine",
    "Thermal Power Station",
    "Solar Panel",
    "Oil Extractor",
    "Oil Refinery",
    "Chemical Plant",
    "Assembler Mk.II",
    "Planetary Logistics Station",
    "Interstellar Logistics Station",
    "Assembler Mk.III",
    "Fractionator",
    "Miniature Particle Collider",
    "Ray Receiver",
    "EM-Rail Ejector",
    "Vertical Launching Silo",
    "Artificial Star",
]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _output_json(data):
    """Print compact JSON to stdout and exit 0."""
    print(json.dumps(data, separators=(",", ":")))
    sys.exit(0)


def _output_error(message, details=None):
    """Print a JSON error object to stdout and exit 1."""
    err = {
        "success": False,
        "error": message,
    }
    if details:
        err["details"] = details
    print(json.dumps(err, separators=(",", ":")))
    sys.exit(1)


def _timeout_handler(_signum, _frame):
    _output_error(
        "Parsing timed out",
        f"Save file processing exceeded {TIMEOUT_SECONDS}s limit.",
    )


# ---------------------------------------------------------------------------
# Extraction helpers — all defensive; return partial data on failure
# ---------------------------------------------------------------------------

def _extract_researched_techs(save):
    """Return list of researched tech dicts from the save object."""
    techs = []
    errors = []

    try:
        # Try several likely attribute names — the parser API is not guaranteed.
        tech_source = None
        for attr in ("game_data", "gameData", "data"):
            candidate = getattr(save, attr, None)
            if candidate is not None:
                tech_source = candidate
                break

        if tech_source is None:
            tech_source = save  # fall back to save object itself

        # Try to find researched techs in the data
        history = None
        for attr in (
            "tech_states", "techStates", "research",
            "history", "gameHistory", "game_history",
        ):
            candidate = getattr(tech_source, attr, None)
            if candidate is not None:
                history = candidate
                break

        if history is None:
            # Maybe it's a dict-like object
            if hasattr(tech_source, "__getitem__"):
                for key in ("tech_states", "techStates", "research"):
                    try:
                        history = tech_source[key]
                        break
                    except (KeyError, TypeError, IndexError):
                        continue

        if history is None:
            errors.append("Could not locate tech/research data in save.")
            return techs, errors

        # history may be a dict {id: state} or a list
        if isinstance(history, dict):
            for tech_id, state in history.items():
                tech_id_int = int(tech_id) if not isinstance(tech_id, int) else tech_id
                unlocked = False
                if isinstance(state, bool):
                    unlocked = state
                elif isinstance(state, (int, float)):
                    unlocked = state > 0
                elif hasattr(state, "unlocked"):
                    unlocked = bool(state.unlocked)
                elif hasattr(state, "researched"):
                    unlocked = bool(state.researched)
                elif hasattr(state, "curLevel"):
                    unlocked = state.curLevel > 0
                elif hasattr(state, "cur_level"):
                    unlocked = state.cur_level > 0

                if unlocked:
                    info = TECH_TREE.get(tech_id_int, {
                        "name": f"Unknown Tech {tech_id_int}",
                        "tier": 0,
                        "category": "unknown",
                    })
                    techs.append({
                        "id": tech_id_int,
                        "name": info["name"],
                        "tier": info["tier"],
                        "category": info["category"],
                    })
        elif hasattr(history, "__iter__"):
            for item in history:
                tech_id_int = None
                if isinstance(item, int):
                    tech_id_int = item
                elif hasattr(item, "id"):
                    tech_id_int = int(item.id)
                elif hasattr(item, "tech_id"):
                    tech_id_int = int(item.tech_id)
                elif hasattr(item, "techId"):
                    tech_id_int = int(item.techId)

                if tech_id_int is not None:
                    info = TECH_TREE.get(tech_id_int, {
                        "name": f"Unknown Tech {tech_id_int}",
                        "tier": 0,
                        "category": "unknown",
                    })
                    techs.append({
                        "id": tech_id_int,
                        "name": info["name"],
                        "tier": info["tier"],
                        "category": info["category"],
                    })
        else:
            errors.append(f"Tech data has unexpected type: {type(history).__name__}")

    except Exception as exc:
        errors.append(f"Error extracting techs: {exc}")

    return techs, errors


def _extract_buildings(save):
    """Return a dict of building counts and a list of errors."""
    buildings = {}
    errors = []

    try:
        # Navigate to factory/entity data
        data_root = None
        for attr in ("game_data", "gameData", "data"):
            candidate = getattr(save, attr, None)
            if candidate is not None:
                data_root = candidate
                break
        if data_root is None:
            data_root = save

        # Try factories / planets
        factories = None
        for attr in ("factories", "factory_data", "factoryData", "planets"):
            candidate = getattr(data_root, attr, None)
            if candidate is not None:
                factories = candidate
                break

        if factories is None and hasattr(data_root, "__getitem__"):
            for key in ("factories", "planets"):
                try:
                    factories = data_root[key]
                    break
                except (KeyError, TypeError, IndexError):
                    continue

        if factories is None:
            errors.append("Could not locate factory/building data in save.")
            return buildings, errors

        factory_list = factories if hasattr(factories, "__iter__") else [factories]

        for factory in factory_list:
            entities = None
            for attr in (
                "entities", "entityPool", "entity_pool",
                "buildings", "buildingPool",
            ):
                candidate = getattr(factory, attr, None)
                if candidate is not None:
                    entities = candidate
                    break

            if entities is None and hasattr(factory, "__getitem__"):
                for key in ("entities", "entityPool", "buildings"):
                    try:
                        entities = factory[key]
                        break
                    except (KeyError, TypeError, IndexError):
                        continue

            if entities is None:
                continue

            for entity in entities:
                name = None
                if hasattr(entity, "name"):
                    name = str(entity.name)
                elif hasattr(entity, "proto_id"):
                    name = f"ProtoId:{entity.proto_id}"
                elif hasattr(entity, "protoId"):
                    name = f"ProtoId:{entity.protoId}"
                elif hasattr(entity, "item_id"):
                    name = f"ItemId:{entity.item_id}"
                elif isinstance(entity, dict):
                    name = entity.get("name") or entity.get("protoId") or "unknown"
                    name = str(name)

                if name:
                    buildings[name] = buildings.get(name, 0) + 1

    except Exception as exc:
        errors.append(f"Error extracting buildings: {exc}")

    return buildings, errors


def _extract_production_stats(save):
    """Return production statistics (items/min) and errors."""
    stats = {}
    errors = []

    try:
        data_root = None
        for attr in ("game_data", "gameData", "data"):
            candidate = getattr(save, attr, None)
            if candidate is not None:
                data_root = candidate
                break
        if data_root is None:
            data_root = save

        stat_source = None
        for attr in (
            "production_statistics", "productionStatistics",
            "statistics", "stats", "factoryProductionStat",
            "production_stat", "productionStat",
        ):
            candidate = getattr(data_root, attr, None)
            if candidate is not None:
                stat_source = candidate
                break

        if stat_source is None and hasattr(data_root, "__getitem__"):
            for key in ("production_statistics", "statistics", "stats"):
                try:
                    stat_source = data_root[key]
                    break
                except (KeyError, TypeError, IndexError):
                    continue

        if stat_source is None:
            errors.append("Could not locate production statistics in save.")
            return stats, errors

        # It might be a dict, a list, or a custom object
        if isinstance(stat_source, dict):
            stats = {str(k): v for k, v in stat_source.items()}
        elif hasattr(stat_source, "__iter__"):
            for entry in stat_source:
                item_name = None
                rate = 0
                if hasattr(entry, "item_name"):
                    item_name = str(entry.item_name)
                elif hasattr(entry, "itemName"):
                    item_name = str(entry.itemName)
                elif hasattr(entry, "name"):
                    item_name = str(entry.name)
                elif isinstance(entry, dict):
                    item_name = str(entry.get("name", entry.get("itemName", "unknown")))

                if hasattr(entry, "production_rate"):
                    rate = entry.production_rate
                elif hasattr(entry, "productionRate"):
                    rate = entry.productionRate
                elif hasattr(entry, "rate"):
                    rate = entry.rate
                elif isinstance(entry, dict):
                    rate = entry.get("rate", entry.get("productionRate", 0))

                if item_name:
                    stats[item_name] = rate
        else:
            # Try to introspect the object for any dict-like data
            if hasattr(stat_source, "__dict__"):
                stats = {
                    k: v for k, v in stat_source.__dict__.items()
                    if not k.startswith("_")
                }
            else:
                errors.append(
                    f"Production stats has unexpected type: {type(stat_source).__name__}"
                )

    except Exception as exc:
        errors.append(f"Error extracting production stats: {exc}")

    return stats, errors


def _extract_inventory(save):
    """Return player inventory as a dict and errors."""
    inventory = {}
    errors = []

    try:
        data_root = None
        for attr in ("game_data", "gameData", "data"):
            candidate = getattr(save, attr, None)
            if candidate is not None:
                data_root = candidate
                break
        if data_root is None:
            data_root = save

        # Find the player or main player inventory
        player = None
        for attr in ("player", "mainPlayer", "main_player"):
            candidate = getattr(data_root, attr, None)
            if candidate is not None:
                player = candidate
                break

        inv_source = None
        if player is not None:
            for attr in ("inventory", "package", "bag", "items"):
                candidate = getattr(player, attr, None)
                if candidate is not None:
                    inv_source = candidate
                    break

        if inv_source is None:
            # Try directly on data_root
            for attr in ("inventory", "player_inventory", "playerInventory"):
                candidate = getattr(data_root, attr, None)
                if candidate is not None:
                    inv_source = candidate
                    break

        if inv_source is None:
            errors.append("Could not locate player inventory in save.")
            return inventory, errors

        if isinstance(inv_source, dict):
            inventory = {str(k): v for k, v in inv_source.items()}
        elif hasattr(inv_source, "grids") or hasattr(inv_source, "items"):
            container = getattr(inv_source, "grids", None) or getattr(inv_source, "items", None)
            if hasattr(container, "__iter__"):
                for slot in container:
                    item_id = None
                    count = 0
                    if hasattr(slot, "item_id"):
                        item_id = slot.item_id
                        count = getattr(slot, "count", getattr(slot, "stack", 1))
                    elif hasattr(slot, "itemId"):
                        item_id = slot.itemId
                        count = getattr(slot, "count", getattr(slot, "stack", 1))
                    elif isinstance(slot, dict):
                        item_id = slot.get("item_id", slot.get("itemId"))
                        count = slot.get("count", slot.get("stack", 1))

                    if item_id and item_id != 0:
                        key = str(item_id)
                        inventory[key] = inventory.get(key, 0) + int(count)
        elif hasattr(inv_source, "__iter__"):
            for item in inv_source:
                if isinstance(item, dict):
                    name = str(item.get("name", item.get("id", "unknown")))
                    count = item.get("count", item.get("amount", 1))
                    inventory[name] = inventory.get(name, 0) + int(count)
                elif hasattr(item, "name"):
                    name = str(item.name)
                    count = getattr(item, "count", getattr(item, "amount", 1))
                    inventory[name] = inventory.get(name, 0) + int(count)
        else:
            errors.append(
                f"Inventory has unexpected type: {type(inv_source).__name__}"
            )

    except Exception as exc:
        errors.append(f"Error extracting inventory: {exc}")

    return inventory, errors


# ---------------------------------------------------------------------------
# Recommendations engine
# ---------------------------------------------------------------------------

def _generate_recommendations(researched_techs, buildings, production_stats):
    """Produce actionable next-step recommendations."""
    recommendations = {
        "next_resource_to_automate": None,
        "next_building_to_place": None,
        "next_tech_to_research": None,
        "notes": [],
    }

    researched_ids = {t["id"] for t in researched_techs}
    researched_categories = {t["category"] for t in researched_techs}
    max_tier = max((t["tier"] for t in researched_techs), default=0)

    # --- Next resource to automate ---
    produced_names_lower = {k.lower() for k in production_stats}
    for milestone in AUTOMATION_MILESTONES:
        # Skip if the tech prerequisite is not met
        if milestone["unlocked_by"] and milestone["unlocked_by"] not in researched_ids:
            continue
        # Check if this resource appears to be produced
        if milestone["resource"].lower() not in produced_names_lower:
            recommendations["next_resource_to_automate"] = milestone["resource"]
            recommendations["notes"].append(
                f"You don't appear to be producing {milestone['resource']} yet. "
                "Setting up automated production will unlock the next tier of progress."
            )
            break

    # --- Next building to place ---
    building_names_lower = {k.lower() for k in buildings}
    for bname in BUILDING_PRIORITY:
        if bname.lower() not in building_names_lower:
            recommendations["next_building_to_place"] = bname
            recommendations["notes"].append(
                f"Consider placing a {bname} to expand your factory capabilities."
            )
            break

    # --- Next tech to research ---
    # Find the lowest-tier unresearched tech that is plausibly next
    unresearched = []
    for tech_id, info in TECH_TREE.items():
        if tech_id not in researched_ids:
            unresearched.append({"id": tech_id, **info})

    # Sort by tier then by id so we suggest the most natural next step
    unresearched.sort(key=lambda t: (t["tier"], t["id"]))

    # Prefer techs whose tier is at most one above the player's max researched tier
    for tech in unresearched:
        if tech["tier"] <= max_tier + 1:
            recommendations["next_tech_to_research"] = {
                "id": tech["id"],
                "name": tech["name"],
                "category": tech["category"],
            }
            recommendations["notes"].append(
                f"Research '{tech['name']}' (ID {tech['id']}) to unlock "
                f"new {tech['category']} capabilities."
            )
            break

    if not recommendations["next_tech_to_research"] and unresearched:
        # Fall back to the overall lowest-tier unresearched tech
        tech = unresearched[0]
        recommendations["next_tech_to_research"] = {
            "id": tech["id"],
            "name": tech["name"],
            "category": tech["category"],
        }

    if not recommendations["notes"]:
        recommendations["notes"].append(
            "Could not determine specific recommendations — "
            "data may be incomplete or the parser returned limited info."
        )

    return recommendations


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    # Set up a timeout so the script never hangs indefinitely.
    # signal.SIGALRM is Unix-only; skip gracefully on Windows.
    if hasattr(signal, "SIGALRM"):
        signal.signal(signal.SIGALRM, _timeout_handler)
        signal.alarm(TIMEOUT_SECONDS)

    # ---- Argument validation ----
    if len(sys.argv) < 2:
        _output_error(
            "No file path provided",
            "Usage: python save_analyzer.py <path_to_save.dsv>",
        )

    filepath = sys.argv[1]

    if not os.path.isfile(filepath):
        _output_error("File not found", f"Path does not exist: {filepath}")

    # Size guard
    try:
        size_mb = os.path.getsize(filepath) / (1024 * 1024)
        if size_mb > MAX_FILE_SIZE_MB:
            _output_error(
                "File too large",
                f"Save file is {size_mb:.1f} MB — refusing to parse files over "
                f"{MAX_FILE_SIZE_MB} MB.",
            )
    except OSError as exc:
        _output_error("Cannot read file metadata", str(exc))

    # ---- Import dsp_save_parser ----
    try:
        from dsp_save_parser import GameSave  # type: ignore[import-untyped]
    except ImportError:
        _output_error(
            "dsp_save_parser is not installed",
            {
                "setup_instructions": [
                    "Install the parser with: pip install dsp-save-parser",
                    "Or from source: pip install git+https://github.com/<author>/dsp-save-parser.git",
                    "Make sure you are using the same Python environment as this script.",
                    f"Current interpreter: {sys.executable}",
                ],
            },
        )

    # ---- Parse the save file ----
    save = None
    parse_errors = []

    try:
        save = GameSave(filepath)
    except TypeError:
        # Some versions want a file-like object instead of a path
        try:
            with open(filepath, "rb") as fh:
                save = GameSave(fh)
        except Exception as inner_exc:
            parse_errors.append(f"Failed to parse save file: {inner_exc}")
    except Exception as exc:
        parse_errors.append(f"Failed to parse save file: {exc}")

    if save is None and not parse_errors:
        parse_errors.append("GameSave returned None — the file may be corrupted.")

    if save is None:
        _output_error("Save parsing failed", parse_errors)

    # ---- Extract data ----
    all_warnings = list(parse_errors)

    techs, tech_errors = _extract_researched_techs(save)
    all_warnings.extend(tech_errors)

    buildings, building_errors = _extract_buildings(save)
    all_warnings.extend(building_errors)

    production, prod_errors = _extract_production_stats(save)
    all_warnings.extend(prod_errors)

    inventory, inv_errors = _extract_inventory(save)
    all_warnings.extend(inv_errors)

    # ---- Generate recommendations ----
    recommendations = _generate_recommendations(techs, buildings, production)

    # ---- Build output ----
    result = {
        "success": True,
        "file": filepath,
        "file_size_mb": round(os.path.getsize(filepath) / (1024 * 1024), 2),
        "researched_technologies": techs,
        "buildings": buildings,
        "production_stats": production,
        "player_inventory": inventory,
        "recommendations": recommendations,
    }

    if all_warnings:
        result["warnings"] = all_warnings

    _output_json(result)


if __name__ == "__main__":
    try:
        main()
    except SystemExit:
        raise
    except Exception:
        # Absolute last resort — never let the script crash without valid JSON
        _output_error("Unexpected error", traceback.format_exc())
