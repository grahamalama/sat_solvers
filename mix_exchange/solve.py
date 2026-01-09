import csv
from itertools import permutations
from enum import StrEnum, auto
from pathlib import Path
from collections import defaultdict

import attrs
from ortools.sat.python import cp_model


class Format(StrEnum):
    USB = auto()
    CD = auto()
    EITHER = auto()


@attrs.define(frozen=True)
class Participant:
    name: str
    can_give: Format = attrs.field(converter=lambda v: Format)
    can_receive: Format = attrs.field(converter=lambda v: Format)


def load_participants(csv_path: str | Path) -> list[Participant]:
    path = Path(csv_path)
    with path.open("r") as f:
        reader = csv.DictReader(f)
        return [Participant(**row) for row in reader]


def can_give(p1: Participant, p2: Participant):
    is_not_self = p1 != p2
    either_is_either = p1.can_give == Format.EITHER or p2.can_receive == Format.EITHER
    formats_match = p1.can_give == p2.can_receive
    return all((is_not_self, (either_is_either or formats_match)))


def find_candidates(
    participants: list[Participant],
) -> dict[Participant, set[Participant]]:
    candidates = defaultdict(set)
    for p1, p2 in permutations(participants, 2):
        if can_give(p1, p2):
            candidates[p1].add(p2)
    return candidates


def create_candidate_variables(
    model: cp_model.CpModel, candidates: dict[Participant, set[Participant]]
) -> dict[str, dict[str, cp_model.IntVar]]:
    candidate_variables = defaultdict(lambda: defaultdict(dict))
    for giver, receivers in candidates.items():
        for receiver in receivers:
            candidate_variables[giver.name][receiver.name] = model.new_bool_var(
                f"{giver.name}_gives_{receiver.name}"
            )
    return candidate_variables


if __name__ == "__main__":
    script_dir = Path(__file__).parent
    participants = load_participants(script_dir / "participants.example.csv")
    candidate_matches = find_candidates(participants)

    model = cp_model.CpModel()
    match_variables = create_candidate_variables(model, candidate_matches)

    # A participate can only give one mix
    for _giver, receivers in match_variables.items():
        model.add_exactly_one(receivers.values())

    # A participate should only receive one mix
    for participant in match_variables.keys():
        participant_is_receiver = []
        for _giver, receivers in match_variables.items():
            if participant in receivers:
                participant_is_receiver.append(receivers[participant])
        model.add_exactly_one(participant_is_receiver)

    solver = cp_model.CpSolver()
    status = solver.Solve(model)

    if status in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        for giver, receivers in match_variables.items():
            for receiver in receivers:
                if solver.Value(match_variables[giver][receiver]) == 1:
                    print(f"{giver} gives to {receiver}")
