"""
LiftSim — Core Data Structures
================================
Design doc: variable structures before building the main loop.
"""

from enum import Enum, auto
import random

# ─── Enums ──────────────────────────────────────────────────────────────

class FlatSize(Enum):
    STUDIO = "studio"   # 1-2 people
    ONE_BR = "1br"      # 1-3 people
    TWO_BR = "2br"      # 2-5 people
    THREE_BR = "3br"    # 3-7 people

class PersonType(Enum):
    WORKER   = auto()
    STUDENT  = auto()
    RETIREE  = auto()
    KID      = auto()
    PET      = auto()
    BABY     = auto()

class Location(Enum):
    HOME     = auto()
    LIFT     = auto()
    LOBBY    = auto()
    OUTSIDE  = auto()

class LiftAlgorithm(Enum):
    FCFS    = "fcfs"
    SCAN    = "scan"
    SMART   = "smart"

class LiftDirection(Enum):
    UP   = 1
    DOWN = -1
    IDLE = 0

class Activity(Enum):
    SLEEPING    = auto()
    MORNING_RUSH = auto()
    AT_WORK     = auto()
    AT_SCHOOL   = auto()
    COMMUTING   = auto()
    RETURNING   = auto()
    HOME        = auto()
    OUTING      = auto()
    WALKING_PET = auto()
    MOVING_IN   = auto()
    MOVING_OUT  = auto()

# ─── Core Data Structures ───────────────────────────────────────────────

# ── Clock ───────────────────────────────────────────────────────────────
SIM_CLOCK = {
    "game_minute": 480,      # Start at 8:00 AM
    "day_of_week": 0,        # Monday
    "speed": 1,              # 1 game-minute per tick (1 real min = 1 game hour)
    "paused": False,
    "game_days_elapsed": 0,
}

# ── Schedule Definitions ──────────────────────────────────────────────
SCHEDULES = {
    "worker_morning": {
        "weekday": {
            "leave": (420, 480),      # 7:00 - 8:00
            "return": (1020, 1080),   # 17:00 - 18:00
            "sleep_end": 360,
            "sleep_start": 1320,
        },
        "weekend": {
            "leave": (600, 780),
            "return": (1020, 1260),
            "sleep_end": 480,
            "sleep_start": 1320,
        },
    },
    "student": {
        "weekday": {
            "leave": (450, 480),
            "return": (900, 960),
            "sleep_end": 390,
            "sleep_start": 1320,
        },
        "weekend": {
            "leave": (600, 900),
            "return": (1020, 1260),
            "sleep_end": 480,
            "sleep_start": 1380,
        },
    },
    "retiree": {
        "weekday": {
            "leave": (420, 480),
            "return": (480, 540),
            "outings": [(600, 660), (840, 900)],
            "sleep_end": 360,
            "sleep_start": 1260,
        },
        "weekend": {
            "leave": (480, 540),
            "return": (540, 600),
            "outings": [(660, 780), (900, 1020)],
            "sleep_end": 360,
            "sleep_start": 1260,
        },
    },
    "kid": {
        "weekday": {
            "leave": (450, 480),
            "return": (900, 960),
            "sleep_end": 420,
            "sleep_start": 1260,
        },
        "weekend": {
            "leave": (540, 780),
            "return": (840, 1080),
            "sleep_end": 480,
            "sleep_start": 1260,
        },
    },
    "pet": {
        "weekday": {
            "walks": [(420, 480), (720, 780), (1140, 1200)],
        },
        "weekend": {
            "walks": [(480, 540), (720, 840), (1140, 1260)],
        },
    },
    "baby": {
        "weekday": {"always_home": True},
        "weekend": {"always_home": True},
    },
}

# ── Building ────────────────────────────────────────────────────────────
BUILDING_CONFIG = {
    "num_floors": 6,
    "num_lifts": 2,
    "top_floor_studio": True,
    "ground_floor_type": "lobby",
}

def generate_default_floors(num_floors: int, top_studio: bool = True) -> dict:
    floors = {}
    floors[0] = []
    for floor in range(1, num_floors):
        is_top = floor == num_floors - 1 and top_studio
        if is_top:
            sizes = [FlatSize.STUDIO] * 4
        else:
            if floor <= num_floors // 2:
                sizes = [FlatSize.THREE_BR, FlatSize.TWO_BR, FlatSize.THREE_BR]
            else:
                sizes = [FlatSize.ONE_BR, FlatSize.TWO_BR, FlatSize.STUDIO, FlatSize.ONE_BR]
        flats = []
        for i, size in enumerate(sizes):
            flat_id = f"{floor}{chr(65 + i)}"
            max_cap = {"studio": 2, "1br": 3, "2br": 5, "3br": 7}[size.value]
            flats.append({
                "id": flat_id, "floor": floor, "position": i,
                "size": size, "max_capacity": max_cap,
                "occupants": [], "furniture": [], "door_open": False,
            })
        floors[floor] = flats
    return floors

# ── Person ──────────────────────────────────────────────────────────────
PEOPLE = {}

def create_person(person_id: str, name: str, age: int,
                  person_type: PersonType, flat_id: str) -> dict:
    type_to_role = {
        PersonType.WORKER: "parent", PersonType.STUDENT: "child",
        PersonType.RETIREE: "elder", PersonType.KID: "child",
        PersonType.PET: "pet", PersonType.BABY: "baby",
    }
    type_to_schedule = {
        PersonType.WORKER: "worker_morning", PersonType.STUDENT: "student",
        PersonType.RETIREE: "retiree", PersonType.KID: "kid",
        PersonType.PET: "pet", PersonType.BABY: "baby",
    }
    return {
        "id": person_id, "name": name, "age": age,
        "type": person_type, "flat_id": flat_id,
        "family_role": type_to_role.get(person_type, "single"),
        "location": Location.HOME, "dest_floor": 0,
        "schedule_profile": type_to_schedule.get(person_type, "worker_morning"),
        "schedule_offset": random.randint(0, 30),
        "weekend_offset": random.randint(0, 120),
        "current_activity": Activity.HOME,
        "heading_home": False,
        "today_leave_time": None,
        "today_return_time": None,
    }

# ── Lift ────────────────────────────────────────────────────────────────
LIFTS = {}

def create_lift(lift_id: int, home_floor: int = 0,
                algorithm: LiftAlgorithm = LiftAlgorithm.SCAN) -> dict:
    return {
        "id": lift_id, "current_floor": home_floor,
        "direction": LiftDirection.IDLE, "target_floors": [],
        "passengers": [], "doors_open": False, "door_timer": 0,
        "algorithm": algorithm, "capacity": 8,
        "floor_buttons": set(),
        "call_queue": {}, "trips_today": 0,
        "moving": False, "progress": 0.0,
    }

# ── Events ──────────────────────────────────────────────────────────────
EVENTS = {
    "move_in_queue": [],
    "move_out_queue": [],
    "active_move": None,
}

# ── Furniture ───────────────────────────────────────────────────────────
FURNITURE_TEMPLATES = {
    "bed":      {"name": "Bed",   "size_units": 2},
    "sofa":     {"name": "Sofa",  "size_units": 3},
    "table":    {"name": "Table", "size_units": 2},
    "wardrobe": {"name": "Wardrobe", "size_units": 3},
    "chair":    {"name": "Chair", "size_units": 1},
    "tv":       {"name": "TV",    "size_units": 1},
    "fridge":   {"name": "Fridge","size_units": 2},
    "box":      {"name": "Box",   "size_units": 1},
}

FURNITURE_BY_FLAT_SIZE = {
    FlatSize.STUDIO:  ["bed", "chair", "table", "tv", "box", "box"],
    FlatSize.ONE_BR:  ["bed", "sofa", "table", "chair", "tv", "wardrobe", "box"],
    FlatSize.TWO_BR:  ["bed", "bed", "sofa", "table", "chair", "tv", "wardrobe", "fridge", "box", "box"],
    FlatSize.THREE_BR: ["bed", "bed", "bed", "sofa", "table", "chair", "tv", "wardrobe", "wardrobe", "fridge", "box", "box", "box"],
}

# ── Stats ───────────────────────────────────────────────────────────────
STATS = {
    "total_residents": 0, "total_families": 0,
    "lift_trips": 0, "avg_wait_time": 0.0,
    "busiest_hour": 8, "busiest_floor": 1,
    "move_ins_today": 0, "move_outs_today": 0,
}

# ── SIMULATION STATE ────────────────────────────────────────────────────
SIM_STATE = {
    "clock": SIM_CLOCK, "building": None,
    "people": PEOPLE, "lifts": LIFTS,
    "events": EVENTS, "stats": STATS,
    "config": BUILDING_CONFIG, "initialized": False,
}
