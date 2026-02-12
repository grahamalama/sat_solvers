# Barcamp Scheduler
#
# Time slots: 10am, 11am, <lunch>, 1pm, 2pm
# Rooms: each has a name and capacity (max attendees)
# Talks: each has a title and vote count from attendees
#
# Solver approach (hybrid constraints + optimization):
#   - Filter: exclude talks with 0 votes (no interest)
#   - Hard constraint: each scheduled talk gets exactly one room+timeslot
#   - Soft constraint: minimize wasted space (room.capacity - talk.votes)
#   - Soft constraint: prefer scheduling talks with more votes
#   - Note: votes can exceed room capacity (we turn people away at the door)
#   - Note: more talks than slots means some won't be scheduled
import argparse
import csv
from dataclasses import dataclass
from datetime import time
from itertools import groupby, product
from pathlib import Path
from typing import Iterable

from ortools.sat.python import cp_model


@dataclass(frozen=True)
class TimeSlot:
    start: time
    end: time


@dataclass(frozen=True)
class Room:
    name: str
    capacity: int  # max attendees (hard limit)

    @classmethod
    def from_row(cls, row: dict):
        return cls(name=row["name"], capacity=int(row["capacity"]))


@dataclass(frozen=True)
class Talk:
    title: str
    votes: int  # used to estimate attendance

    @classmethod
    def from_row(cls, row: dict):
        return cls(title=row["title"], votes=int(row["votes"]))


@dataclass(frozen=True)
class ScheduledTalk:
    talk: Talk
    room: Room
    timeslot: TimeSlot


def load_rooms(path: Path):
    with path.open("r") as f:
        reader = csv.DictReader(f)
        return [Room.from_row(row) for row in reader]


def load_talks(path: Path):
    with path.open("r") as f:
        reader = csv.DictReader(f)
        return [Talk.from_row(row) for row in reader]


def generate_timeslots(*args, slot_duration_minutes=50):
    for i in (args):
        start = time(i, 0, 0, 0)
        end = time(i, slot_duration_minutes, 0, 0)
        yield TimeSlot(start=start, end=end)


def solve(
    timeslots: Iterable[TimeSlot],
    rooms: Iterable[Room],
    talks: Iterable[Talk],
):
    model = cp_model.CpModel()

    scheduled_talks = {}

    for timeslot, room, talk in product(timeslots, rooms, talks):
        var_name = f"{timeslot.start}_{talk.title}_{room.name}"
        scheduled_talk = ScheduledTalk(talk=talk, room=room, timeslot=timeslot)
        scheduled_talks[scheduled_talk] = model.new_bool_var(var_name)

    # Hard constraint: each talk scheduled at most once
    by_talk = sorted(scheduled_talks.keys(), key=lambda s: s.talk.title)
    for _, options in groupby(by_talk, key=lambda s: s.talk):
        model.add_at_most_one([scheduled_talks[s] for s in options])

    # Hard constraint: each room-timeslot has at most one talk
    by_slot = sorted(
        scheduled_talks.keys(), key=lambda s: (s.room.name, s.timeslot.start)
    )
    for _, options in groupby(by_slot, key=lambda s: (s.room, s.timeslot)):
        model.add_at_most_one([scheduled_talks[s] for s in options])

    model.Maximize(
        sum(
            min(st.talk.votes, st.room.capacity) * var
            for (st, var) in scheduled_talks.items()
        )
    )

    solver = cp_model.CpSolver()
    status = solver.solve(model)
    if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        raise Exception(":(")

    scheduled = [st for (st, var) in scheduled_talks.items() if solver.Value(var) == 1]
    return scheduled


def print_schedule(scheduled: list[ScheduledTalk]):
    by_time = sorted(scheduled, key=lambda s: (s.timeslot.start, s.room.name))

    current_slot = None
    for st in by_time:
        if st.timeslot != current_slot:
            current_slot = st.timeslot
            print(f"\n{current_slot.start.strftime('%I:%M %p')} - {current_slot.end.strftime('%I:%M %p')}")
            print("-" * 50)

        attendance = min(st.talk.votes, st.room.capacity)
        overflow = max(0, st.talk.votes - st.room.capacity)
        print(f"  {st.room.name:<15} (cap {st.room.capacity}) | {st.talk.title} ({st.talk.votes} votes)")
        print(f"  {'':<15}          | {attendance} attending, {overflow} turned away")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--rooms", default="data/barcamp/rooms.csv", type=Path)
    parser.add_argument("--talks", default="data/barcamp/talks.csv", type=Path)
    args = parser.parse_args()

    timeslots = generate_timeslots(10, 11, 13, 14)
    rooms = load_rooms(args.rooms)
    talks = load_talks(args.talks)

    schedule = solve(timeslots, rooms, talks)
    print_schedule(schedule)
