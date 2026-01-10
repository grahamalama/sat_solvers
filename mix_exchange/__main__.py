import argparse
from pathlib import Path

from mix_exchange.solve import load_participants, solve_exchange

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
