#!/usr/bin/env python3
"""
save_analyzer.py — Parse a DSP .dsv save file and output JSON recommendations.
Always outputs valid JSON, even on errors.
"""

import json
import os
import sys
import traceback

# Add bundled dsp_save_parser_lib to import path
_lib_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "dsp_save_parser_lib")
if os.path.isdir(_lib_dir) and _lib_dir not in sys.path:
    sys.path.insert(0, _lib_dir)

# Bootstrap the code generator (creates *_generated.py from format.txt)
try:
    from dsp_save_parser.generator import generate_parser
    pkg_dir = os.path.join(_lib_dir, "dsp_save_parser")
    for fmt_file in ("save_format.txt", "blueprint_format.txt"):
        src = os.path.join(pkg_dir, fmt_file)
        dst = os.path.join(pkg_dir, fmt_file.replace(".txt", "_generated.py"))
        if os.path.exists(src) and not os.path.exists(dst):
            generate_parser(src, dst)
except Exception:
    pass

# DSP Tech IDs (from the game's internal numbering)
TECH_NAMES = {
    1: "Basic Logistics System",
    1001: "Electromagnetic Matrix", 1002: "Energy Matrix", 1003: "Structure Matrix",
    1004: "Information Matrix", 1005: "Gravity Matrix", 1006: "Universe Matrix",
    1101: "Automatic Metallurgy", 1102: "Smelting Purification", 1103: "Crystal Smelting",
    1104: "Steel Smelting", 1105: "Polymer Chemical Engineering", 1111: "High-Efficiency Plasma Extract",
    1112: "Plasma Extract Refining", 1113: "X-Ray Cracking",
    1120: "Thruster", 1121: "Reinforced Thruster", 1122: "Logistics Carrier Engine",
    1131: "Interstellar Logistics System", 1132: "Gas Giant Exploitation",
    1133: "Planetary Logistics Station", 1134: "Interstellar Logistics Station",
    1141: "High-Strength Titanium Alloy", 1142: "Particle Container",
    1143: "Strange Matter", 1144: "Graviton Lens", 1145: "Space Warper",
    1151: "Miniature Particle Collider",
    1201: "Basic Assembling Processes", 1202: "Improved Logistics System",
    1203: "High-Speed Assembling Processes", 1204: "Advanced Logistics System",
    1205: "Quantum Printing",
    1301: "Solar Collection", 1302: "Photon Frequency Conversion",
    1303: "Plane Smelter", 1304: "Quantum Chemical Engineering",
    1311: "Semiconductor Material", 1312: "Processor",
    1401: "Applied Superconductor", 1402: "Superconducting Electronics",
    1403: "Super-Magnetic Field Generator",
    1411: "High-Efficiency Rotating Reactor", 1412: "Miniature Fusion Power",
    1413: "Energy Exchanger", 1414: "Ray Receiver",
    1501: "Electromagnetic Drive", 1502: "Magnetic Levitation Technology",
    1503: "Particle Magnetic Drive", 1504: "Gravity Wave Refraction",
    1505: "Gravitational Lens Research",
    1511: "Solar Sail Orbit System", 1512: "EM-Rail Ejector",
    1521: "Vertical Launching Silo", 1522: "Dyson Sphere Stress System",
    1523: "Dyson Sphere Program",
    1601: "Mechanical Frame", 1602: "Dyson Sphere Component",
    1603: "Universe Exploration", 1604: "Mission Accomplished!",
    1701: "Magnetic Turbine Breakthrough",
    1711: "Planetary Ionosphere Utilization",
    1901: "Mining Efficiency", 1902: "Veins Utilization",
    2101: "Drive Engine Lv1", 2102: "Drive Engine Lv2", 2103: "Drive Engine Lv3", 2104: "Drive Engine Lv4",
    2201: "Mecha Core Lv1", 2202: "Mecha Core Lv2", 2203: "Mecha Core Lv3",
    2301: "Communication Control", 2302: "Drone Engine Lv1", 2303: "Drone Engine Lv2",
    2501: "Sorter Cargo Stacking Lv1", 2502: "Sorter Cargo Stacking Lv2", 2503: "Sorter Cargo Stacking Lv3",
    2601: "Research Speed Lv1", 2602: "Research Speed Lv2", 2603: "Research Speed Lv3", 2604: "Research Speed Lv4",
    2801: "Universe Exploration Lv1", 2802: "Universe Exploration Lv2", 2803: "Universe Exploration Lv3", 2804: "Universe Exploration Lv4",
    3101: "Proliferator Mk.I", 3102: "Proliferator Mk.II", 3103: "Proliferator Mk.III",
}

# Priority research order (what to research next, roughly)
RESEARCH_PRIORITY = [
    1001, 1002, 1201, 1301, 1311, 1401, 1501, 1502, 1202, 1101, 1105,
    1133, 1003, 1102, 1141, 1142, 1312, 1402, 1302, 1303, 1412,
    1131, 1134, 1004, 1143, 1144, 1145, 1151, 1203, 1503, 1304,
    1511, 1512, 1601, 1602, 1521, 1522, 1005, 1523, 1006, 1604,
]

UPGRADE_PRIORITY = [
    2101, 2102, 2201, 2301, 2302, 2501, 2601, 2602, 2103, 2202,
    2502, 2303, 2603, 2104, 2203, 2503, 2604, 2801, 2802, 2803, 2804,
    1901, 1902, 3101, 3102, 3103,
]

# Building proto IDs to names (common ones)
BUILDING_NAMES = {
    2001: "Conveyor Belt Mk.I", 2002: "Conveyor Belt Mk.II", 2003: "Conveyor Belt Mk.III",
    2011: "Sorter Mk.I", 2012: "Sorter Mk.II", 2013: "Sorter Mk.III",
    2020: "Splitter", 2040: "Traffic Monitor", 2030: "Spray Coater",
    2101: "Storage Mk.I", 2102: "Storage Mk.II", 2106: "Storage Tank",
    2103: "Planetary Logistics Station", 2104: "Interstellar Logistics Station",
    2105: "Orbital Collector",
    2201: "Tesla Tower", 2202: "Wireless Power Tower", 2203: "Satellite Substation",
    2204: "Wind Turbine", 2211: "Thermal Power Station", 2205: "Solar Panel",
    2206: "Accumulator", 2207: "Full Accumulator", 2208: "Energy Exchanger",
    2212: "Mini Fusion Power Station", 2210: "Artificial Star", 2209: "Ray Receiver",
    2301: "Mining Machine", 2302: "Advanced Mining Machine",
    2303: "Water Pump", 2304: "Oil Extractor",
    2302: "Advanced Mining Machine",
    2303: "Water Pump", 2304: "Oil Extractor",
    2310: "Fractionator",
    2309: "Chemical Plant", 2317: "Quantum Chemical Plant",
    2308: "Oil Refinery",
    2303: "Water Pump",
    2305: "Arc Smelter", 2315: "Plane Smelter",
    2306: "Assembler Mk.I", 2307: "Assembler Mk.II", 2318: "Assembler Mk.III",
    2313: "EM-Rail Ejector", 2311: "Miniature Particle Collider",
    2312: "Matrix Lab",
    2314: "Vertical Launching Silo",
    2316: "Re-composing Assembler",
}



def output_json(data):
    json.dump(data, sys.stdout, indent=2, default=str)
    sys.stdout.write("\n")


def main():
    if len(sys.argv) < 2:
        output_json({"error": "No save file path provided", "setup": "Usage: python save_analyzer.py <path_to.dsv>"})
        return

    filepath = sys.argv[1]
    if not os.path.isfile(filepath):
        output_json({"error": f"File not found: {filepath}"})
        return

    file_size_mb = os.path.getsize(filepath) / (1024 * 1024)

    try:
        from dsp_save_parser import GameSave
    except ImportError:
        output_json({
            "error": "dsp_save_parser not available",
            "setup": "Run: git clone https://github.com/qhgz2013/dsp_save_parser.git dsp_save_parser_lib"
        })
        return

    # Parse the save
    try:
        with open(filepath, "rb") as f:
            save = GameSave.parse(f)
    except Exception as e:
        output_json({"error": "Failed to parse save file", "detail": str(e)})
        return

    result = {
        "success": True,
        "file": os.path.basename(filepath),
        "file_size_mb": round(file_size_mb, 1),
        "summary": "",
        "recommendations": {
            "next_buildings": [],
            "next_research": [],
            "next_upgrades": [],
        },
    }

    try:
        gd = save.game_data
        history = gd.history

        # --- Researched techs ---
        unlocked_tech_ids = set()
        in_progress_tech_ids = set()
        for ts in history.tech_state:
            if ts.unlocked:
                unlocked_tech_ids.add(ts.id)
            elif ts.hash_uploaded > 0 and not ts.unlocked:
                in_progress_tech_ids.add(ts.id)

        unlocked_recipes = set(history.recipe_unlocked)

        # --- Count buildings across all factories ---
        building_counts = {}
        total_buildings = 0
        for factory in gd.factories:
            try:
                for entity in factory.entity_pool:
                    try:
                        pid = entity.proto_id
                        if pid and pid > 0:
                            name = BUILDING_NAMES.get(pid, f"Unknown ({pid})")
                            building_counts[name] = building_counts.get(name, 0) + 1
                            total_buildings += 1
                    except:
                        pass
            except:
                pass

        # --- Summary ---
        num_techs = len(unlocked_tech_ids)
        num_recipes = len(unlocked_recipes)
        result["summary"] = (
            f"Game: {gd.game_name} | "
            f"Tick: {gd.game_tick:,} | "
            f"Techs researched: {num_techs} | "
            f"Recipes unlocked: {num_recipes} | "
            f"Buildings placed: {total_buildings:,} | "
            f"Save size: {file_size_mb:.1f} MB"
        )

        # --- Recommendations: Next research ---
        for tid in RESEARCH_PRIORITY:
            if tid not in unlocked_tech_ids and tid not in in_progress_tech_ids:
                name = TECH_NAMES.get(tid, f"Tech {tid}")
                result["recommendations"]["next_research"].append({
                    "name": name,
                    "priority": "high" if len(result["recommendations"]["next_research"]) < 2 else "medium",
                    "reason": "Next in standard research progression"
                })
                if len(result["recommendations"]["next_research"]) >= 5:
                    break

        # --- Recommendations: Next upgrade ---
        for tid in UPGRADE_PRIORITY:
            if tid not in unlocked_tech_ids:
                # Check if it's a leveled tech — find current level
                name = TECH_NAMES.get(tid, f"Tech {tid}")
                result["recommendations"]["next_upgrades"].append({
                    "name": name,
                    "priority": "high" if len(result["recommendations"]["next_upgrades"]) < 2 else "medium",
                    "reason": "Next upgrade in priority order"
                })
                if len(result["recommendations"]["next_upgrades"]) >= 5:
                    break

        # --- Collect what's actually being produced by assemblers/smelters ---
        # Product item IDs that have an active production building
        automated_product_ids = set()
        for factory in gd.factories:
            try:
                fs = factory.factory_system
                for asm in fs.assembler_pool:
                    try:
                        if asm.products:
                            for pid in asm.products:
                                if pid and pid > 0:
                                    automated_product_ids.add(pid)
                    except:
                        pass
            except:
                pass

        # Map building names to the item proto IDs that represent them
        # (these are what shows up in assembler .products when you craft the building)
        BUILDING_ITEM_IDS = {
            "Tesla Tower": 2201, "Wireless Power Tower": 2202,
            "Satellite Substation": 2203, "Wind Turbine": 2204,
            "Thermal Power Station": 2211, "Solar Panel": 2205,
            "Accumulator": 2206, "Mini Fusion Power Station": 2212,
            "Energy Exchanger": 2208, "Ray Receiver": 2209,
            "Conveyor Belt Mk.I": 2001, "Conveyor Belt Mk.II": 2002, "Conveyor Belt Mk.III": 2003,
            "Sorter Mk.I": 2011, "Sorter Mk.II": 2012, "Sorter Mk.III": 2013,
            "Splitter": 2020, "Spray Coater": 2030, "Traffic Monitor": 2040,
            "Storage Mk.I": 2101, "Storage Mk.II": 2102, "Storage Tank": 2106,
            "Planetary Logistics Station": 2103, "Interstellar Logistics Station": 2104,
            "Orbital Collector": 2105,
            "Mining Machine": 2301, "Water Pump": 2303, "Oil Extractor": 2304,
            "Arc Smelter": 2305, "Plane Smelter": 2315,
            "Assembler Mk.I": 2306, "Assembler Mk.II": 2307, "Assembler Mk.III": 2318,
            "Chemical Plant": 2309, "Oil Refinery": 2308,
            "Fractionator": 2310, "Miniature Particle Collider": 2311,
            "Matrix Lab": 2312, "EM-Rail Ejector": 2313,
            "Vertical Launching Silo": 2314,
        }

        # --- Recommendations: Next building to automate ---
        # Buildings you're placing but NOT producing in any assembler
        common_buildings = [
            "Mining Machine", "Arc Smelter", "Assembler Mk.I", "Tesla Tower",
            "Conveyor Belt Mk.I", "Sorter Mk.I", "Splitter",
            "Wind Turbine", "Thermal Power Station", "Solar Panel",
            "Assembler Mk.II", "Conveyor Belt Mk.II", "Sorter Mk.II",
            "Matrix Lab", "Oil Refinery", "Chemical Plant", "Fractionator",
            "Planetary Logistics Station", "Interstellar Logistics Station",
            "Mini Fusion Power Station", "EM-Rail Ejector", "Vertical Launching Silo",
        ]
        for bname in common_buildings:
            item_id = BUILDING_ITEM_IDS.get(bname)
            is_automated = item_id and item_id in automated_product_ids
            if is_automated:
                continue  # Already being produced — skip
            count = building_counts.get(bname, 0)
            if count > 0:
                result["recommendations"]["next_buildings"].append({
                    "name": bname,
                    "priority": "high" if count >= 10 else "medium",
                    "reason": f"You have {count} placed but no assembler producing them"
                })
            if len(result["recommendations"]["next_buildings"]) >= 5:
                break

        # --- Export raw data for client-side use ---
        # Map all known item proto IDs to names
        ITEM_ID_TO_NAME = {
            1101: "Iron Ingot", 1102: "Copper Ingot", 1104: "Magnet",
            1105: "Titanium Ingot", 1106: "Steel", 1108: "Stone Brick",
            1109: "Glass", 1110: "Energetic Graphite", 1112: "High-Purity Silicon",
            1113: "Diamond", 1114: "Crystal Silicon", 1115: "Titanium Alloy",
            1120: "Refined Oil", 1121: "Sulfuric Acid",
            1201: "Gear", 1202: "Magnetic Coil", 1203: "Electric Motor",
            1204: "Electromagnetic Turbine", 1205: "Super-Magnetic Ring",
            1206: "Particle Container", 1207: "Strange Matter",
            1208: "Graviton Lens", 1209: "Space Warper",
            1301: "Circuit Board", 1302: "Processor", 1303: "Quantum Chip",
            1304: "Microcrystalline Component", 1305: "Plane Filter",
            1401: "Plastic", 1402: "Graphene", 1403: "Carbon Nanotube",
            1404: "Organic Crystal", 1405: "Titanium Crystal", 1406: "Casimir Crystal",
            1501: "Prism", 1502: "Plasma Exciter", 1503: "Photon Combiner",
            1141: "Particle Broadband", 1142: "Titanium Glass",
            1143: "Annihilation Constraint Sphere",
            1601: "Proliferator Mk.I", 1602: "Proliferator Mk.II", 1603: "Proliferator Mk.III",
            1801: "Hydrogen Fuel Rod", 1802: "Deuteron Fuel Rod", 1803: "Antimatter Fuel Rod",
            1804: "Foundation",
            1901: "Electromagnetic Matrix", 1902: "Energy Matrix", 1903: "Structure Matrix",
            1904: "Information Matrix", 1905: "Gravity Matrix", 1906: "Universe Matrix",
            5001: "Solar Sail", 5002: "Small Carrier Rocket",
            5003: "Frame Material", 5004: "Dyson Sphere Component",
        }
        # Merge building IDs
        ITEM_ID_TO_NAME.update(BUILDING_ITEM_IDS)

        automated_names = sorted(set(
            ITEM_ID_TO_NAME.get(pid, f"Unknown ({pid})")
            for pid in automated_product_ids
            if pid in ITEM_ID_TO_NAME
        ))
        result["automated_product_ids"] = sorted(list(automated_product_ids))
        result["automated_product_names"] = automated_names
        result["building_counts"] = building_counts

    except Exception as e:
        result["error_detail"] = f"Analysis partially failed: {str(e)}"
        result["traceback"] = traceback.format_exc()

    output_json(result)


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        output_json({"error": f"Fatal error: {str(e)}", "traceback": traceback.format_exc()})
