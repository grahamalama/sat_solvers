import argparse
import csv
from dataclasses import dataclass
from itertools import groupby, permutations
from pathlib import Path

from ortools.sat.python import cp_model


@dataclass(frozen=True)
class Participant:
    name: str
    can_give: str
    can_receive: str


def load_participants(path):
    with path.open("r") as f:
        return [Participant(**row) for row in csv.DictReader(f)]


def can_exchange(giver, receiver):
    if giver == receiver:
        return False
    return (
        giver.can_give == "either"
        or receiver.can_receive == "either"
        or giver.can_give == receiver.can_receive
    )


def find_valid_pairs(participants):
    return [
        (giver, receiver)
        for giver, receiver in permutations(participants, 2)
        if can_exchange(giver, receiver)
    ]


def solve(participants):
    model = cp_model.CpModel()

    valid_pairs = find_valid_pairs(participants)
    assign = {pair: model.new_bool_var(f"assign_{i}") for i, pair in enumerate(valid_pairs)}

    # Constraint: each participant gives exactly one mix
    by_giver = sorted(valid_pairs, key=lambda p: p[0].name)
    for _, options in groupby(by_giver, key=lambda p: p[0]):
        model.add_exactly_one([assign[pair] for pair in options])

    # Constraint: each participant receives exactly one mix
    by_receiver = sorted(valid_pairs, key=lambda p: p[1].name)
    for _, options in groupby(by_receiver, key=lambda p: p[1]):
        model.add_exactly_one([assign[pair] for pair in options])

    # Constraint: no direct swaps (A→B and B→A)
    for pair in valid_pairs:
        reverse = (pair[1], pair[0])
        if reverse in assign:
            model.add_at_most_one([assign[pair], assign[reverse]])

    solver = cp_model.CpSolver()
    status = solver.Solve(model)

    if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        return None

    return {
        giver: receiver
        for (giver, receiver), var in assign.items()
        if solver.Value(var)
    }


def print_solution(solution):
    if solution:
        print("Mix Exchange Solution:")
        for giver, receiver in solution.items():
            print(f"  {giver.name} → {receiver.name}")
    else:
        print("No solution found.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("csv_file", type=Path)
    args = parser.parse_args()

    participants = load_participants(args.csv_file)
    solution = solve(participants)
    print_solution(solution)
