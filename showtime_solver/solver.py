from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timedelta
from itertools import combinations

from ortools.sat.python import cp_model

BUFFER_TIME_MINUTES = 10

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


@dataclass
class Showtime:
    id: int
    title: str
    start: datetime
    end: datetime
    theater: str
    runtime_minutes: int


def can_go(earlier: Showtime, later: Showtime) -> bool:
    walk = THEATER_TRAVEL_TIMES_MINUTES[earlier.theater][later.theater]
    arrival = earlier.end + timedelta(minutes=walk + BUFFER_TIME_MINUTES)
    return arrival <= later.start


def solve(shows):
    show_list = []
    for idx, show in enumerate(shows):
        show_list.append(
            Showtime(
                idx,
                show["title"],
                show["start_dt"],
                show["end_dt"],
                show["theater"],
                show["runtime_minutes"],
            )
        )
    # Group showings by movie title for the "exactly one per movie" rule
    by_title = defaultdict(list)
    for st in show_list:
        by_title[st.title].append(st.id)

    # Precompute infeasible pairs (order-aware: earlier -> later must be possible)
    infeasible_pairs = []
    for a, b in combinations(show_list, 2):  # all unique unordered pairs
        # figure out which starts first
        earlier, later = (a, b) if a.start <= b.start else (b, a)
        if not can_go(earlier, later):
            infeasible_pairs.append((earlier.id, later.id))

    # ----------------------
    # MODEL
    # ----------------------
    model = cp_model.CpModel()

    # One Bool per showing: attend or not
    attend = {show.id: model.new_bool_var(f"attend_{show.id}") for show in show_list}

    # Exactly one showing per movie title
    for title, ids in by_title.items():
        model.add_exactly_one([attend[i] for i in ids])

    # Forbid infeasible pairs: never attend both
    for i, j in infeasible_pairs:
        model.add_at_most_one([attend[i], attend[j]])

    # ----------------------
    # SOLVE
    # ----------------------
    solver = cp_model.CpSolver()
    status = solver.Solve(model)

    if status in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        chosen = [st for st in show_list if solver.Value(attend[st.id]) == 1]
        # Sort by start time to get the watch order
        chosen.sort(key=lambda s: s.start)

        print("Feasible schedule:")
        for st in chosen:
            print(
                f"{st.start.strftime('%a %b %d %I:%M %p')} — {st.end.strftime('%I:%M %p')}"
                f"  | {st.title}  @ {st.theater}  ({st.runtime_minutes}m)"
            )
    else:
        print(
            "No feasible way to see each movie exactly once with the given travel/buffer constraints."
        )
