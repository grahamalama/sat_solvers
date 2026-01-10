import csv
from collections import defaultdict
from enum import StrEnum, auto
from itertools import permutations
from pathlib import Path

import attrs
from ortools.sat.python import cp_model


class Format(StrEnum):
    USB = auto()
    CD = auto()
    EITHER = auto()


@attrs.define(frozen=True)
class Participant:
    name: str
    can_give: Format = attrs.field(converter=Format)
    can_receive: Format = attrs.field(converter=Format)


def load_participants(csv_path: str | Path) -> list[Participant]:
    path = Path(csv_path)
    with path.open("r") as f:
        reader = csv.DictReader(f)
        return [Participant(**row) for row in reader]


def can_give(p1: Participant, p2: Participant) -> bool:
    if p1 == p2:
        return False
    return any(
        (
            p1.can_give == Format.EITHER,
            p2.can_receive == Format.EITHER,
            p1.can_give == p2.can_receive,
        )
    )


def find_candidates(
    participants: list[Participant],
) -> dict[Participant, set[Participant]]:
    candidates = defaultdict(set)
    for p1, p2 in permutations(participants, 2):
        if can_give(p1, p2):
            candidates[p1].add(p2)
    return candidates


def create_match_variables(
    model: cp_model.CpModel, candidates: dict[Participant, set[Participant]]
) -> dict[tuple[Participant, Participant], cp_model.IntVar]:
    """Create boolean variables for each valid (giver, receiver) pair."""
    variables = {}
    for giver, receivers in candidates.items():
        for receiver in receivers:
            variables[(giver, receiver)] = model.new_bool_var(
                f"{giver.name}_gives_{receiver.name}"
            )
    return variables


if __name__ == "__main__":
    script_dir = Path(__file__).parent
    participants = load_participants(script_dir / "participants.example.csv")
    candidate_matches = find_candidates(participants)

    model = cp_model.CpModel()
    match_variables = create_match_variables(model, candidate_matches)

    # A participant can only give one mix
    for participant in candidate_matches.keys():
        gives_to = (
            var for (giver, _), var in match_variables.items() if giver == participant
        )
        model.add_exactly_one(gives_to)

    # A participant should only receive one mix
    for participant in candidate_matches.keys():
        receives_from = (
            var
            for (_, receiver), var in match_variables.items()
            if receiver == participant
        )
        model.add_exactly_one(receives_from)

    # prevent pairs (A gives to B and B gives to A)
    for (giver, receiver), var in match_variables.items():
        reverse_pair = (receiver, giver)
        if reverse_pair in match_variables:
            model.add_at_most_one([var, match_variables[reverse_pair]])

    solver = cp_model.CpSolver()
    status = solver.Solve(model)

    if status in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        for (giver, receiver), var in match_variables.items():
            if solver.Value(var) == 1:
                print(f"{giver.name} gives to {receiver.name}")
