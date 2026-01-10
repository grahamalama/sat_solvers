"""
Mix Exchange Solver using OR-Tools CP-SAT

A Secret Santa-style music mix exchange where participants can give/receive
mixes in different formats (USB, CD, or either).
"""

import argparse
import csv
from dataclasses import dataclass
from itertools import permutations
from pathlib import Path

from ortools.sat.python import cp_model


@dataclass(frozen=True)
class Participant:
    name: str
    can_give: str
    can_receive: str


def load_participants(csv_path: Path) -> list[Participant]:
    """Load participants from a CSV file."""
    with csv_path.open() as f:
        return [Participant(**row) for row in csv.DictReader(f)]


def can_exchange(giver: Participant, receiver: Participant) -> bool:
    """Check if a giver can give to a receiver based on format compatibility."""
    if giver == receiver:
        return False

    # Either party accepts any format, or formats match
    return (
        giver.can_give == "either"
        or receiver.can_receive == "either"
        or giver.can_give == receiver.can_receive
    )


def find_valid_pairs(
    participants: list[Participant],
) -> list[tuple[Participant, Participant]]:
    """Find all valid (giver, receiver) pairs."""
    return [
        (p1, p2) for p1, p2 in permutations(participants, 2) if can_exchange(p1, p2)
    ]


def solve_exchange(participants: list[Participant]) -> dict[Participant, Participant]:
    """
    Solve the mix exchange problem using CP-SAT.

    Returns a dict mapping each giver to their receiver.
    """
    valid_pairs = find_valid_pairs(participants)

    # Create the model
    model = cp_model.CpModel()

    # Create a boolean variable for each valid (giver, receiver) pair
    pair_vars = {
        (giver, receiver): model.new_bool_var(f"{giver.name}_to_{receiver.name}")
        for giver, receiver in valid_pairs
    }

    # Constraint 1: Each participant gives exactly one mix
    for participant in participants:
        gives_to = [
            var for (giver, _), var in pair_vars.items() if giver == participant
        ]
        model.add_exactly_one(gives_to)

    # Constraint 2: Each participant receives exactly one mix
    for participant in participants:
        receives_from = [
            var for (_, receiver), var in pair_vars.items() if receiver == participant
        ]
        model.add_exactly_one(receives_from)

    # Constraint 3: Prevent direct swaps (A→B and B→A)
    for (giver, receiver), var in pair_vars.items():
        reverse = (receiver, giver)
        if reverse in pair_vars:
            model.add_at_most_one([var, pair_vars[reverse]])

    # Solve (with deterministic settings for reproducibility)
    solver = cp_model.CpSolver()
    solver.parameters.random_seed = 42
    solver.parameters.num_workers = 1
    status = solver.Solve(model)

    if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        raise ValueError("No solution found!")

    # Extract solution
    return {
        giver: receiver
        for (giver, receiver), var in pair_vars.items()
        if solver.Value(var) == 1
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Solve a music mix exchange using CP-SAT"
    )
    parser.add_argument(
        "csv_file", type=Path, help="Path to the CSV file containing participant data"
    )
    args = parser.parse_args()

    participants = load_participants(args.csv_file)
    solution = solve_exchange(participants)

    # Print results
    print("Mix Exchange Solution:")
    for giver, receiver in solution.items():
        print(f"  {giver.name} → {receiver.name}")
