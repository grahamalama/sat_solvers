import argparse
import csv
from dataclasses import dataclass
from datetime import datetime, timedelta
from itertools import combinations, groupby
from pathlib import Path

from ortools.sat.python import cp_model


@dataclass(frozen=True)
class Film:
    title: str
    runtime_minutes: int
    rank: int


@dataclass(frozen=True)
class Showing:
    film: Film
    start_dt: datetime
    end_dt: datetime
    theater: str

    @classmethod
    def from_csv_row(cls, row):
        return cls(
            film=Film(
                title=row["title"],
                runtime_minutes=int(row["runtime_minutes"]),
                rank=int(row["rank"]),
            ),
            start_dt=datetime.fromisoformat(row["start_dt"]),
            end_dt=datetime.fromisoformat(row["end_dt"]),
            theater=row["theater"],
        )


BUFFER_MINUTES = 10

THEATER_TRAVEL_MINUTES = {
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


def load_showings(path):
    with path.open("r") as f:
        return [Showing.from_csv_row(row) for row in csv.DictReader(f)]


def can_attend_both(one: Showing, other: Showing):
    earlier, later = sorted([one, other], key=lambda s: s.start_dt)
    travel_minutes = THEATER_TRAVEL_MINUTES[earlier.theater][later.theater]
    return (
        earlier.end_dt + timedelta(minutes=travel_minutes + BUFFER_MINUTES)
        <= later.start_dt
    )


def find_conflicts(showings) -> list[tuple[Showing, Showing]]:
    return [
        conflict
        for conflict in combinations(showings, 2)
        if not can_attend_both(*conflict)
    ]


def solve(showings):
    model = cp_model.CpModel()

    attend = {
        showing: model.new_bool_var(f"attend_{count}")
        for count, showing in enumerate(showings, start=1)
    }

    # Constraint: attend at most one showing per movie
    by_title = sorted(showings, key=lambda s: s.film.title)
    for _, options in groupby(by_title, key=lambda s: s.film.title):
        model.add_at_most_one([attend[s] for s in options])

    # Constraint: can't attend conflicting showings
    for one, other in find_conflicts(showings):
        model.add_at_most_one([attend[one], attend[other]])

    # Objective: maximize weighted sum based on film rankings
    # Lower rank number = higher priority, so invert the weights
    max_rank = max(s.film.rank for s in showings)
    model.maximize(
        sum((max_rank + 1 - s.film.rank) * attend[s] for s in showings)
    )

    solver = cp_model.CpSolver()
    status = solver.solve(model)

    if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        return []

    return sorted(
        [s for s in showings if solver.value(attend[s])],
        key=lambda s: s.start_dt,
    )


def print_schedule(schedule, all_showings):
    if schedule:
        print(f"Optimized schedule ({len(schedule)} films):")
        for showing in schedule:
            print(
                f"{showing.start_dt.strftime('%a %b %d %I:%M %p')} — "
                f"{showing.end_dt.strftime('%I:%M %p')}  | {showing.film.title}  "
                f"@ {showing.theater}  ({showing.film.runtime_minutes}m)"
            )

        # Identify dropped films
        scheduled_titles = {s.film.title for s in schedule}
        all_titles = {s.film.title for s in all_showings}
        dropped_titles = all_titles - scheduled_titles

        if dropped_titles:
            # Get rank info for dropped films
            dropped_films = sorted(
                [s.film for s in all_showings if s.film.title in dropped_titles],
                key=lambda f: f.rank
            )
            # Deduplicate by title (multiple showings per film)
            seen = set()
            unique_dropped = []
            for film in dropped_films:
                if film.title not in seen:
                    seen.add(film.title)
                    unique_dropped.append(film)

            print(f"\nDropped films ({len(unique_dropped)}):")
            for film in unique_dropped:
                print(f"  Rank {film.rank}: {film.title}")
    else:
        print("No feasible schedule found.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--showings", type=Path, default="data/festival/ranked_showings.csv")
    args = parser.parse_args()

    showings = load_showings(args.showings)
    schedule = solve(showings)
    print_schedule(schedule, showings)
