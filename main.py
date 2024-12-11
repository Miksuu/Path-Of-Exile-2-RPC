import datetime
import json
import os
import re
import time
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional

import psutil
from pypresence import Presence


class CharacterClass(Enum):
    MERCENARY = "Mercenary"
    MONK = "Monk"
    RANGER = "Ranger"
    SORCERESS = "Sorceress"
    WARRIOR = "Warrior"
    WITCH = "Witch"

    def get_ascendencies(self) -> Optional[List["ClassAscendency"]]:
        return {
            CharacterClass.MERCENARY: [
                ClassAscendency.WITCHHUNTER,
                ClassAscendency.GEMLING_LEGIONNAIRE,
            ],
            CharacterClass.MONK: [
                ClassAscendency.ACOLYTE_OF_CHAYULA,
                ClassAscendency.INVOKER,
            ],
            CharacterClass.RANGER: [
                ClassAscendency.DEADEYE,
                ClassAscendency.PATHFINDER,
            ],
            CharacterClass.SORCERESS: [
                ClassAscendency.CHRONOMANCER,
                ClassAscendency.STORMWEAVER,
            ],
            CharacterClass.WARRIOR: [
                ClassAscendency.TITAN,
                ClassAscendency.WARBRINGER,
            ],
            CharacterClass.WITCH: [
                ClassAscendency.BLOOD_MAGE,
                ClassAscendency.INFERNALIST,
            ],
        }.get(self)


class ClassAscendency(Enum):
    WITCHHUNTER = "Witchhunter"
    GEMLING_LEGIONNAIRE = "Gemling Legionnaire"
    ACOLYTE_OF_CHAYULA = "Acolyte of Chayula"
    INVOKER = "Invoker"
    DEADEYE = "Deadeye"
    PATHFINDER = "Pathfinder"
    CHRONOMANCER = "Chronomancer"
    STORMWEAVER = "Stormweaver"
    TITAN = "Titan"
    WARBRINGER = "Warbringer"
    BLOOD_MAGE = "Blood Mage"
    INFERNALIST = "Infernalist"

    def get_class(self) -> CharacterClass:
        return {
            ClassAscendency.WITCHHUNTER: CharacterClass.MERCENARY,
            ClassAscendency.GEMLING_LEGIONNAIRE: CharacterClass.MERCENARY,
            ClassAscendency.ACOLYTE_OF_CHAYULA: CharacterClass.MONK,
            ClassAscendency.INVOKER: CharacterClass.MONK,
            ClassAscendency.DEADEYE: CharacterClass.RANGER,
            ClassAscendency.PATHFINDER: CharacterClass.RANGER,
            ClassAscendency.CHRONOMANCER: CharacterClass.SORCERESS,
            ClassAscendency.STORMWEAVER: CharacterClass.SORCERESS,
            ClassAscendency.TITAN: CharacterClass.WARRIOR,
            ClassAscendency.WARBRINGER: CharacterClass.WARRIOR,
            ClassAscendency.BLOOD_MAGE: CharacterClass.WITCH,
            ClassAscendency.INFERNALIST: CharacterClass.WITCH,
        }[self]


def find_game_log():
    for process in psutil.process_iter():
        try:
            if process.name() == "PathOfExileSteam.exe":
                full_path = process.exe()
                game_dir = os.path.dirname(full_path)
                return os.path.join(game_dir, "logs", "Client.txt")
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    return None


def load_locations():
    file_path = Path("locations.json")
    if not file_path.exists():
        return {}
    with file_path.open("r", encoding="utf-8") as f:
        try:
            data = json.load(f)
            return data.get("areas", {})
        except Exception:
            return {}


def determine_location(area_name: str, locations: Dict[str, str]) -> Optional[str]:
    normalized_area_name = area_name
    if area_name.startswith("C_"):
        normalized_area_name = area_name[2:]

    for key, value in locations.items():
        if normalized_area_name == key or normalized_area_name == value:
            return value
    return None


def find_last_level_up(line: str, regex_level: re.Pattern) -> Optional[Dict[str, str]]:
    if match := regex_level.search(line):
        username, ascension_class, level = match.groups()
        ascension_class = ascension_class.strip()
        try:
            if ascension_class in ClassAscendency._value2member_map_:
                base_class = ClassAscendency(ascension_class).get_class().value
            else:
                base_class = "Unknown"
        except Exception:
            base_class = "Unknown"
        return {
            "username": username,
            "ascension_class": ascension_class,
            "base_class": base_class,
            "level": level,
        }
    return None


def get_last_level_up(
    log_file_path: Path, regex_level: re.Pattern
) -> Optional[Dict[str, str]]:
    try:
        with log_file_path.open("r", encoding="utf-8") as log_file:
            lines = log_file.readlines()
            for line in reversed(lines):
                if match := regex_level.search(line):
                    return find_last_level_up(line, regex_level)
    except Exception:
        pass
    return None


def find_instance(
    line: str, regex_instance: re.Pattern, locations: Dict[str, str]
) -> Optional[Dict[str, str]]:
    if match := regex_instance.search(line):
        level, area_name, seed = match.groups()
        location_name = determine_location(area_name, locations)
        return {
            "location_name": location_name or area_name,
            "location_level": level,
        }
    return None


def update_rpc(level_info, instance_info=None):
    rpc.update(
        details=f"{level_info['username']} ({level_info['base_class']} | {level_info['ascension_class']} - Lvl {level_info['level']})",
        state=f"In game..." if not instance_info else f"In: {instance_info['location_name']} (Lvl {instance_info['location_level']})",
        start=int(datetime.datetime.now().timestamp()),
    )


def monitor_log():
    game_path = find_game_log()
    if not game_path:
        return

    log_file_path = Path(game_path)
    regex_level = re.compile(r": (\w+) \(([\w\s]+)\) is now level (\d+)")
    regex_instance = re.compile(
        r'Generating level (\d+) area "([^"]+)" with seed (\d+)'
    )
    locations = load_locations()

    last_level_info = get_last_level_up(log_file_path, regex_level)
    if last_level_info:
        rpc.update(
            details=f"{last_level_info['username']} ({last_level_info['base_class']} | {last_level_info['ascension_class']} - Lvl {last_level_info['level']})",
            state="In game...",
            start=int(datetime.datetime.now().timestamp()),
        )

    with log_file_path.open("r", encoding="utf-8") as log_file:
        log_file.seek(0, 2)

        current_status = {"level_info": last_level_info, "instance_info": None}

        while True:
            new_lines = log_file.readlines()
            for line in new_lines:
                level_info = find_last_level_up(line, regex_level)
                if level_info and (
                    not current_status["level_info"]
                    or level_info != current_status["level_info"]
                ):
                    current_status["level_info"] = level_info
                    update_rpc(level_info, current_status["instance_info"])

                instance_info = find_instance(line, regex_instance, locations)
                if instance_info and (
                    not current_status["instance_info"]
                    or instance_info != current_status["instance_info"]
                ):
                    current_status["instance_info"] = instance_info
                    update_rpc(current_status["level_info"], instance_info)

            time.sleep(5)


if __name__ == "__main__":
    rpc = Presence("1315800372207419504")
    rpc.connect()
    monitor_log()
