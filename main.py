#!.venv/bin/python

import pathlib
import argparse
from showtime_solver.selector import (
    load_program,
    parse_program,
    write_showtimes,
    select_interested_movies,
    SHOWTIME_FILE,
    read_showtimes,
)
from showtime_solver.solver import solve

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Solve showtime schedules.")
    parser.add_argument(
        "--keep-selections",
        action="store_true",
        help="Skip selecting interested movies and keep previous selections.",
    )
    parser.add_argument(
        "--refresh-showtimes",
        action="store_true",
        help="Re-fetch and re-parse the program, overwriting the CSV.",
    )
    args = parser.parse_args()

    if args.refresh_showtimes or not SHOWTIME_FILE.exists():
        showtimes = parse_program(load_program())
        write_showtimes(showtimes)

    if not args.keep_selections:
        select_interested_movies(pathlib.Path(SHOWTIME_FILE))

    showtimes = read_showtimes(SHOWTIME_FILE)
    solve(showtimes)
