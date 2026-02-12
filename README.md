# SAT Solvers

Constraint programming examples using OR-Tools.

## Getting Started

This project uses `uv` for dependency management. If you don't have `uv` installed:

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

## Usage

```bash
uv run solvers/sudoku.py
uv run solvers/mix_exchange.py data/mix_exchange/participants.csv
uv run solvers/festival.py data/festival/showtime_data.csv
uv run solvers/barcamp.py data/barcamp/sessions.csv
```
