import argparse
from itertools import batched, product

from ortools.sat.python import cp_model

DIGITS = (1, 2, 3, 4, 5, 6, 7, 8, 9)
EXAMPLE_PUZZLE = (
    "...26.7.168..7..9.19...45..82.1...4...46.29...5...3.28..93...74.4..5..367.3.18..."
)


def solve(puzzle_input):
    model = cp_model.CpModel()

    puzzle = {
        (row, col): model.new_int_var(1, 9, f"r{row}c{col}")
        for row, col in product(DIGITS, repeat=2)
    }

    for row in DIGITS:
        model.add_all_different([puzzle[row, col] for col in DIGITS])

    for col in DIGITS:
        model.add_all_different([puzzle[row, col] for row in DIGITS])

    for bands in product(((1, 2, 3), (4, 5, 6), (7, 8, 9)), repeat=2):
        model.add_all_different([puzzle[cell] for cell in product(*bands)])

    for row_index, row_chars in enumerate(batched(puzzle_input, 9), start=1):
        for col_index, char in enumerate(row_chars, start=1):
            if char.isdigit() and char != "0":
                model.add(puzzle[row_index, col_index] == int(char))

    solver = cp_model.CpSolver()
    status = solver.solve(model)

    if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        raise ValueError("No solution found")

    return "".join([str(solver.value(puzzle[cell])) for cell in product(DIGITS, repeat=2)])


def print_puzzle(puzzle):
    for i, line in enumerate(batched(puzzle, n=9)):
        bands = ["".join(band) for band in batched(line, n=3)]
        print(*"|".join(bands))
        if i == 2 or i == 5:
            print("------+-------+------")


if __name__ == "__main__":

    def puzzle_str(value):
        if len(value) != 81:
            raise argparse.ArgumentTypeError(
                f"Expected 81 characters, got {len(value)}"
            )
        return value

    parser = argparse.ArgumentParser()
    parser.add_argument("puzzle", nargs="?", type=puzzle_str)
    args = parser.parse_args()
    if not args.puzzle:
        print("Using example puzzle: ", EXAMPLE_PUZZLE)
    puzzle_input = args.puzzle or EXAMPLE_PUZZLE
    solved_puzzle = solve(puzzle_input)
    print("INPUT")
    print_puzzle(puzzle_input)
    print("")
    print("SOLVED")
    print_puzzle(solved_puzzle)