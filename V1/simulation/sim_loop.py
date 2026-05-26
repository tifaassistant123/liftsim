"""
LiftSim — Core Simulation Update Logic
========================================
Real-time-based simulation: clock, people, lifts, events.
"""
import random
import time
from simulation.data_structures import (
    SIM_CLOCK, PEOPLE, LIFTS, EVENTS, STATS, BUILDING_CONFIG, SIM_STATE,
    Location, LiftDirection, Activity, PersonType,
    SCHEDULES,
)

# ── Clock ────────────────────────────────────────────────────────────────

_LAST_TICK_TIME = None  # Real-time tracking for clock

def tick_clock():
    """
    Advance the simulation clock based on real elapsed time.
    Target: 1 real second = 1 game minute (at speed=1).
    So 1 real minute = 1 game hour. ✅
    """
    global _LAST_TICK_TIME

    if SIM_CLOCK["paused"]:
        _LAST_TICK_TIME = None
        return

    now = time.time()
    if _LAST_TICK_TIME is None:
        _LAST_TICK_TIME = now
        return

    elapsed = now - _LAST_TICK_TIME  # Real seconds elapsed
    _LAST_TICK_TIME = now

    speed = SIM_CLOCK["speed"]
    # Convert real seconds to game minutes (1 real sec = 1 game min at speed=1)
    game_minutes = elapsed * speed

    # Accumulate fractional minutes
    if "_accumulator" not in SIM_CLOCK:
        SIM_CLOCK["_accumulator"] = 0.0
    SIM_CLOCK["_accumulator"] += game_minutes
    to_add = int(SIM_CLOCK["_accumulator"])
    SIM_CLOCK["_accumulator"] -= to_add

    if to_add > 0:
        SIM_CLOCK["game_minute"] += to_add
        # Handle day rollover
        while SIM_CLOCK["game_minute"] >= 1440:
            SIM_CLOCK["game_minute"] -= 1440
            SIM_CLOCK["day_of_week"] = (SIM_CLOCK["day_of_week"] + 1) % 7
            SIM_CLOCK["game_days_elapsed"] += 1
            on_new_day()

def get_time_str(game_minute):
    """Convert game minutes to HH:MM string."""
    h = (game_minute // 60) % 24
    m = game_minute % 60
    return f"{h:02d}:{m:02d}"

def get_day_name(day_of_week):
    return ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"][day_of_week]

def is_weekend():
    return SIM_CLOCK["day_of_week"] >= 5

# ── Daily Reset ──────────────────────────────────────────────────────────

def on_new_day():
    """Called when a new in-game day starts.
    Re-randomizes today's departure/return times for each person.
    """
    # Reset daily stats (don't clear LIFTS — that destroys lifts!)
    STATS["move_ins_today"] = 0
    STATS["move_outs_today"] = 0
    for lift in LIFTS.values():
        lift["trips_today"] = 0
        lift["call_queue"] = {}
        lift["floor_buttons"] = set()
        lift["passengers"] = []

    # Re-randomize each person's schedule for today
    for person in PEOPLE.values():
        profile = SCHEDULES.get(person["schedule_profile"])
        if not profile:
            continue

        day_type = "weekend" if is_weekend() else "weekday"
        day_sched = profile.get(day_type, profile.get("weekday", {}))

        offset = person["schedule_offset"]
        weekend_extra = person["weekend_offset"] if is_weekend() else 0
        total_offset = offset + weekend_extra

        if "leave" in day_sched and "return" in day_sched:
            l_start, l_end = day_sched["leave"]
            r_start, r_end = day_sched["return"]

            # Apply offset, clamp to valid range
            l_start = min(l_start + total_offset, 1439)
            l_end = min(l_end + total_offset, 1439)
            r_start = min(r_start + total_offset, 1439)
            r_end = min(r_end + total_offset, 1439)

            # Randomize exact time within window
            if l_end > l_start:
                person["today_leave_time"] = random.randint(l_start, l_end - 1)
            else:
                person["today_leave_time"] = l_start

            if r_end > r_start:
                person["today_return_time"] = random.randint(r_start, r_end - 1)
            else:
                person["today_return_time"] = r_start

        elif "always_home" in day_sched:
            person["today_leave_time"] = None
            person["today_return_time"] = None

        elif "outings" in day_sched:
            # Retirees/pets with multiple outings
            outings = []
            for o_start, o_end in day_sched["outings"]:
                o_start = min(o_start + total_offset, 1439)
                o_end = min(o_end + total_offset, 1439)
                if o_end > o_start:
                    outings.append(random.randint(o_start, o_end - 1))
                else:
                    outings.append(o_start)
            person["today_leave_time"] = outings[0] if outings else None
            person["today_return_time"] = outings[-1] if len(outings) > 1 else None

        # Reset location to HOME at start of day
        if person["location"] in (Location.LOBBY, Location.OUTSIDE, Location.LIFT):
            person["location"] = Location.HOME
            person["heading_home"] = False

    # Generate some events for today (moved in/out)
    generate_daily_events()

def generate_daily_events():
    """Randomly generate move-in/move-out events for today."""
    # Small chance of move events per day
    if random.random() < 0.15:  # ~15% chance any given day
        # Find a vacant flat
        vacant_flats = []
        for floor, flats in SIM_STATE.get("building", {}).items():
            if floor == 0:
                continue
            for flat in flats:
                if len(flat["occupants"]) == 0 or random.random() < 0.05:
                    vacant_flats.append(flat["id"])

        if vacant_flats:
            target = random.choice(vacant_flats)
            EVENTS["move_in_queue"].append({
                "day": SIM_CLOCK["game_days_elapsed"],
                "flat_id": target,
                "family_size": random.choices([1, 2, 3, 4, 5], weights=[3, 3, 2, 1, 1])[0],
                "has_pets": random.random() < 0.3,
                "furniture_count": random.randint(3, 8),
                "status": "pending",
            })

# ── People Updates ───────────────────────────────────────────────────────

def update_people():
    """Check each person's schedule and update their location/activity."""
    now = SIM_CLOCK["game_minute"]

    for person in PEOPLE.values():
        flat_id = person["flat_id"]
        # Find which floor this person lives on
        home_floor = get_flat_floor(flat_id)
        if home_floor is None:
            continue

        # Check if it's time for this person to do something
        person_type = person["type"]

        # ── Leave home ──
        if person["location"] == Location.HOME:
            leave_time = person.get("today_leave_time")
            if leave_time is not None and now >= leave_time:
                # Person wants to leave — they need to call the lift
                person["location"] = Location.LOBBY
                person["current_activity"] = Activity.MORNING_RUSH
                person["heading_home"] = False
                person["dest_floor"] = 0  # Going to ground floor

                # Register a lift call from their floor going DOWN
                call_lift_from_floor(home_floor, "down")

        # ── Return home ──
        elif person["location"] in (Location.LOBBY, Location.OUTSIDE) and not person["heading_home"]:
            return_time = person.get("today_return_time")
            if return_time is not None and now >= return_time:
                person["heading_home"] = True
                person["location"] = Location.LOBBY
                person["current_activity"] = Activity.RETURNING
                person["dest_floor"] = home_floor

                # Register a lift call from ground floor going UP
                call_lift_from_floor(0, "up")

def get_flat_floor(flat_id):
    """Find which floor a flat is on."""
    building = SIM_STATE.get("building", {})
    for floor, flats in building.items():
        for flat in flats:
            if flat["id"] == flat_id:
                return floor
    return None

# ── Lift System ─────────────────────────────────────────────────────────

def call_lift_from_floor(floor, direction):
    """Register a lift call from a floor."""
    for lift in LIFTS.values():
        if floor not in lift["call_queue"]:
            lift["call_queue"][floor] = {"up": False, "down": False}
        lift["call_queue"][floor][direction] = True

def update_lifts():
    """Process all lifts: move, board, disembark."""
    for lift in LIFTS.values():
        update_single_lift(lift)

def update_single_lift(lift):
    """Process one lift's state machine."""
    if lift["direction"] == LiftDirection.IDLE:
        # Check if there are any pending calls
        if lift["call_queue"] or lift["floor_buttons"]:
            # Find the nearest requested floor to start moving
            all_requests = set(lift["call_queue"].keys()) | lift["floor_buttons"]
            nearest = min(all_requests, key=lambda f: abs(f - lift["current_floor"]))
            if nearest > lift["current_floor"]:
                lift["direction"] = LiftDirection.UP
            elif nearest < lift["current_floor"]:
                lift["direction"] = LiftDirection.DOWN
        return

    # Moving
    floor = lift["current_floor"]
    direction = lift["direction"].value

    # Check if we should stop at this floor
    should_stop = False
    if floor in lift["call_queue"]:
        call = lift["call_queue"][floor]
        if direction == 1 and call.get("up"):
            should_stop = True
        elif direction == -1 and call.get("down"):
            should_stop = True
    if floor in lift["floor_buttons"]:
        should_stop = True

    if should_stop:
        # Open doors, let passengers on/off
        lift["doors_open"] = True
        lift["door_timer"] = 30  # Game-minutes to keep door open

        # Disembark passengers whose floor is here
        remaining = []
        for p_id in lift["passengers"]:
            person = PEOPLE.get(p_id)
            if person and person["dest_floor"] == floor:
                person["location"] = Location.HOME if floor != 0 else Location.LOBBY
                if person["heading_home"]:
                    person["current_activity"] = Activity.HOME
                else:
                    person["location"] = Location.OUTSIDE
                    person["current_activity"] = Activity.AT_WORK
            else:
                remaining.append(p_id)
        lift["passengers"] = remaining

        # Board passengers waiting at this floor
        for person in PEOPLE.values():
            if person["flat_id"] is None:
                continue
            p_floor = get_flat_floor(person["flat_id"])
            if p_floor is None:
                continue

            if person["location"] == Location.LOBBY and p_floor == floor:
                if person["dest_floor"] is not None and len(lift["passengers"]) < lift["capacity"]:
                    lift["passengers"].append(person["id"])
                    person["location"] = Location.LIFT

        # Clear call for this floor/direction
        if floor in lift["call_queue"]:
            if direction == 1:
                lift["call_queue"][floor]["up"] = False
            else:
                lift["call_queue"][floor]["down"] = False
            # Clean up empty entries
            if not any(lift["call_queue"][floor].values()):
                del lift["call_queue"][floor]
        lift["floor_buttons"].discard(floor)

        lift["target_floors"] = list(set(lift["target_floors"]) - {floor})

    # Door timer countdown
    if lift["doors_open"]:
        lift["door_timer"] -= SIM_CLOCK["speed"]
        if lift["door_timer"] <= 0:
            lift["doors_open"] = False

    # Move between floors (one game-tick movement)
    if not lift["doors_open"]:
        # Check if we reached the end and need to reverse
        max_floor = BUILDING_CONFIG["num_floors"] - 1
        if lift["current_floor"] >= max_floor and direction == 1:
            lift["direction"] = LiftDirection.DOWN
        elif lift["current_floor"] <= 0 and direction == -1:
            lift["direction"] = LiftDirection.UP

        # Advance progress or move floor
        lift["progress"] += 0.1 * (SIM_CLOCK["speed"] / 5)
        if lift["progress"] >= 1.0:
            lift["progress"] = 0.0
            lift["current_floor"] += direction

            # If no more requests, go idle
            if not lift["call_queue"] and not lift["floor_buttons"] and not lift["passengers"]:
                lift["direction"] = LiftDirection.IDLE

# ── Main Update ─────────────────────────────────────────────────────────

def init_simulation(config_override: dict = None):
    """Initialize the simulation with building, people, and lifts."""
    from simulation.data_structures import generate_default_floors, create_person, create_lift

    # Apply config overrides
    if config_override:
        BUILDING_CONFIG.update(config_override)

    # Generate building
    floors = generate_default_floors(
        BUILDING_CONFIG["num_floors"],
        BUILDING_CONFIG["top_floor_studio"]
    )
    SIM_STATE["building"] = floors

    # Create lifts
    for i in range(BUILDING_CONFIG["num_lifts"]):
        lift = create_lift(i, home_floor=0)
        LIFTS[i] = lift

    # Generate initial residents
    from simulation.data_structures import FURNITURE_BY_FLAT_SIZE, FURNITURE_TEMPLATES
    person_count = 0
    for floor, flats in floors.items():
        if floor == 0:
            continue
        for flat in flats:
            # Fill each flat with a random family
            family_size = random.randint(
                1, flat["max_capacity"]
            )
            flat["occupants"] = []

            # Determine family composition
            if family_size == 1:
                types = [random.choice([PersonType.WORKER, PersonType.RETIREE, PersonType.STUDENT])]
                ages = [random.randint(18, 75)]
            elif family_size == 2:
                if random.random() < 0.5:
                    types = [PersonType.WORKER, PersonType.WORKER]  # Couple
                    ages = [random.randint(22, 45), random.randint(22, 45)]
                else:
                    types = [PersonType.WORKER, PersonType.KID]  # Single parent + kid
                    ages = [random.randint(25, 50), random.randint(4, 12)]
            elif family_size == 3:
                types = [PersonType.WORKER, PersonType.WORKER, PersonType.KID]
                ages = [random.randint(25, 45), random.randint(25, 45), random.randint(3, 12)]
            elif family_size >= 4:
                types = [PersonType.WORKER, PersonType.WORKER, PersonType.KID, PersonType.KID]
                ages = [random.randint(28, 50), random.randint(28, 50), random.randint(3, 8), random.randint(8, 16)]
            elif family_size >= 5:
                types = [PersonType.WORKER, PersonType.WORKER, PersonType.KID, PersonType.KID, PersonType.KID]
                ages = [random.randint(30, 50), random.randint(30, 50), random.randint(2, 6), random.randint(6, 12), random.randint(10, 18)]

            # Truncate to actual family_size
            types = types[:family_size]
            ages = ages[:family_size]

            for j, (ptype, age) in enumerate(zip(types, ages)):
                p_id = f"resident_{person_count:04d}"
                p = create_person(
                    p_id,
                    f"Res{p_id[-4:]}",
                    age,
                    ptype,
                    flat["id"]
                )
                PEOPLE[p_id] = p
                flat["occupants"].append(p_id)
                person_count += 1

            # Add furniture
            size_key = flat["size"]
            template_list = FURNITURE_BY_FLAT_SIZE.get(size_key, ["box", "box"])
            flat["furniture"] = [
                {
                    "id": f"furn_{flat['id']}_{i}",
                    **FURNITURE_TEMPLATES.get(f, {"name": "📦 Box", "size_units": 1}),
                    "being_moved": False,
                }
                for i, f in enumerate(template_list)
            ]

    STATS["total_residents"] = len(PEOPLE)
    STATS["total_families"] = len([f for flats in floors.values() for f in flats if f["occupants"]])

    # Set initial daily times
    on_new_day()

    SIM_STATE["initialized"] = True
    return SIM_STATE

def update_simulation():
    """Main simulation tick — called every frame."""
    tick_clock()
    update_people()
    update_lifts()
