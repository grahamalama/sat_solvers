"""
Movie Schedule Solver using OR-Tools CP-SAT

Finds a feasible schedule to see multiple movies across different theaters,
accounting for travel time between theaters and buffer time between showings.

The problem: Given multiple showtimes for each movie across different theaters,
choose exactly one showing per movie such that you can physically attend all of
them (with enough time to travel between theaters).
"""

from collections import defaultdict
from datetime import timedelta
from itertools import combinations

from ortools.sat.python import cp_model

from showtime_solver.models import Showtime

# Configuration constants
BUFFER_TIME_MINUTES = 10  # Extra time needed between movies (bathroom, snacks, etc.)

# Travel times between Philadelphia theaters (in minutes)
THEATER_TRAVEL_TIMES_MINUTES = {
    "Film Society East": {
        "Film Society Bourse": 8,
        "Film Society Center": 30,
        "Film Society East": 0,
    },
    "Film Society Bourse": {
        "Film Society East": 8,
        "Film Society Center": 25,
        "Film Society Bourse": 0,
    },
    "Film Society Center": {
        "Film Society East": 30,
        "Film Society Bourse": 25,
        "Film Society Center": 0,
    },
}


def can_attend_both(earlier: Showtime, later: Showtime) -> bool:
    """
    Check if you can physically attend both showings.

    Returns True if there's enough time to finish the earlier showing,
    travel to the later theater, and arrive with buffer time.
    """
    travel_minutes = THEATER_TRAVEL_TIMES_MINUTES[earlier.theater][later.theater]
    arrival_time = earlier.end_dt + timedelta(minutes=travel_minutes + BUFFER_TIME_MINUTES)
    return arrival_time <= later.start_dt


def find_conflicting_pairs(showtimes: list[Showtime]) -> list[tuple[str, str]]:
    """
    Find all pairs of showtimes that cannot both be attended.

    Returns a list of (id1, id2) tuples representing impossible combinations.
    """
    conflicts = []

    for a, b in combinations(showtimes, 2):
        # Order by start time
        earlier, later = (a, b) if a.start_dt <= b.start_dt else (b, a)

        # If we can't make it from earlier to later, they conflict
        if not can_attend_both(earlier, later):
            conflicts.append((earlier.id, later.id))

    return conflicts


def solve_schedule(showtimes: list[Showtime]) -> list[Showtime] | None:
    """
    Find a feasible schedule to see one showing of each movie.

    Returns:
        List of Showtime objects sorted by start time, or None if no solution exists.
    """
    # Group showtimes by movie title
    showtimes_by_movie = defaultdict(list)
    for showing in showtimes:
        showtimes_by_movie[showing.title].append(showing.id)

    # Find all pairs that conflict (can't attend both)
    conflicts = find_conflicting_pairs(showtimes)

    # Create the constraint model
    model = cp_model.CpModel()

    # Create a boolean variable for each showtime: attend it or not?
    attend = {
        showing.id: model.new_bool_var(f"attend_{showing.id}") for showing in showtimes
    }

    # Constraint 1: Attend exactly one showing per movie
    for movie_title, showing_ids in showtimes_by_movie.items():
        model.add_exactly_one([attend[sid] for sid in showing_ids])

    # Constraint 2: Never attend both showings in a conflicting pair
    for id1, id2 in conflicts:
        model.add_at_most_one([attend[id1], attend[id2]])

    # Solve (with deterministic settings for reproducibility)
    solver = cp_model.CpSolver()
    solver.parameters.random_seed = 42
    solver.parameters.num_workers = 1
    status = solver.Solve(model)

    if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        return None

    # Extract and sort the chosen showtimes
    chosen = [showing for showing in showtimes if solver.Value(attend[showing.id]) == 1]
    chosen.sort(key=lambda s: s.start_dt)

    return chosen


def solve(showtimes: list[Showtime]) -> None:
    """
    Solve the schedule and print results.

    This is the main entry point called by the CLI.
    """
    schedule = solve_schedule(showtimes)

    if schedule:
        print("Feasible schedule:")
        for showing in schedule:
            print(
                f"{showing.start_dt.strftime('%a %b %d %I:%M %p')} — "
                f"{showing.end_dt.strftime('%I:%M %p')}  | {showing.title}  "
                f"@ {showing.theater}  ({showing.runtime_minutes}m)"
            )
    else:
        print(
            "No feasible way to see each movie exactly once with the given "
            "travel/buffer constraints."
        )
