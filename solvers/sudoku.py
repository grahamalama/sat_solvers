import argparse
from itertools import batched, chain, product

from ortools.sat.python import cp_model

EXAMPLE_PUZZLE = (
    "...26.7.168..7..9.19...45..82.1...4...46.29...5...3.28..93...74.4..5..367.3.18..."
)


def solve(puzzle_input):
    model = cp_model.CpModel()

    puzzle = [
        [model.new_int_var(1, 9, f"r{row}c{col}") for col in range(9)]
        for row in range(9)
    ]

    for row in puzzle:
        model.add_all_different(row)

    for col in zip(*puzzle):
        model.add_all_different(col)

    bands = (0, 1, 2), (3, 4, 5), (6, 7, 8)
    for rows, cols in product(bands, repeat=2):
        model.add_all_different([puzzle[row][col] for row in rows for col in cols])

    for index, char in enumerate(puzzle_input):
        if char.isdigit() and char != "0":
            row, col = divmod(index, 9)
            model.add(puzzle[row][col] == int(char))

    solver = cp_model.CpSolver()
    status = solver.solve(model)

    if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        raise ValueError("No solution found")

    return "".join(
        str(solver.value(cell)) for cell in chain.from_iterable(puzzle)
    )


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
