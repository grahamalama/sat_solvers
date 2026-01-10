"""
Festival showtime data management - fetching, parsing, and selection.
"""

import csv
import pathlib
import shutil
import sys
import textwrap
from dataclasses import asdict
from datetime import datetime, timedelta

import questionary
import requests
from bs4 import BeautifulSoup

from showtime_solver.models import Showtime

URL = "https://filmadelphia.org/festival/films/"
DATA_DIR = pathlib.Path(__file__).parent / "data"
HTML_FILE = DATA_DIR / "program.html"
SHOWTIME_FILE = DATA_DIR / "showtimes.csv"
FESTIVAL_YEAR = 2025

SHOWTIME_HEADERS = [
    "title",
    "description",
    "start_dt",
    "end_dt",
    "theater",
    "runtime_minutes",
    "interested",
]


def fetch_program(url: str) -> str:
    """Fetch HTML content from a URL."""
    print(f"Fetching HTML from {url} ...", file=sys.stderr)
    response = requests.get(url, timeout=15)
    response.raise_for_status()
    return response.text


def load_program() -> str:
    """Load HTML from file if it exists, otherwise fetch it."""
    DATA_DIR.mkdir(exist_ok=True)

    if not HTML_FILE.exists():
        program_html = fetch_program(URL)
        HTML_FILE.write_text(program_html)
        print(f"Saved HTML to {HTML_FILE}", file=sys.stderr)
    else:
        print(f"Using cached HTML from {HTML_FILE}", file=sys.stderr)

    return HTML_FILE.read_text()


def parse_program(html: str) -> list[Showtime]:
    """Extract movie showtimes from the HTML."""
    soup = BeautifulSoup(html, "html.parser")
    shows = []

    for movie in soup.select(".movie-tags"):
        title_tag = movie.select_one(".text-xl.font-bold a")
        title = title_tag.get_text(strip=True) if title_tag else "N/A"

        description_tag = title_tag.parent.find_next_sibling() if title_tag else None
        description = description_tag.get_text(strip=True) if description_tag else ""

        runtime_span = movie.find("span", string=lambda s: s and "Runtime" in s)
        runtime_minutes = 0
        if runtime_span:
            parent = runtime_span.find_parent()
            if parent:
                runtime_minutes = int(
                    parent.get_text(strip=True)
                    .replace("Runtime:", "")
                    .replace("min", "")
                    .strip()
                )

        showtime_blocks = movie.select(".flex-wrap.mt-4.md\\:flex")

        for block in showtime_blocks:
            date = None
            theater = None
            for element in block.find_all(["div", "a"], recursive=False):
                if element.name == "div":
                    text = element.get_text(strip=True)
                    if "," in text:
                        date = text
                    elif "Film Society" in text:
                        theater = text
                elif element.name == "a" and "button-showtime" in element.get("class", []):
                    time = element.get_text(strip=True)
                    if date and time and theater:
                        start_dt = datetime.strptime(
                            f"{date} {time};{FESTIVAL_YEAR}",
                            "%a, %b %d %I:%M%p;%Y",
                        )
                        end_dt = start_dt + timedelta(minutes=runtime_minutes)
                        shows.append(
                            Showtime(
                                title=title,
                                description=description,
                                start_dt=start_dt,
                                end_dt=end_dt,
                                theater=theater,
                                runtime_minutes=runtime_minutes,
                                interested=False,
                            )
                        )

    # Deduplicate by converting to set and back (Showtime is hashable)
    return list(set(shows))


def write_showtimes(showtimes: list[Showtime]) -> None:
    """Write showtimes to CSV file."""
    DATA_DIR.mkdir(exist_ok=True)
    SHOWTIME_FILE.touch()
    with SHOWTIME_FILE.open("w") as f:
        writer = csv.DictWriter(f, fieldnames=SHOWTIME_HEADERS, extrasaction="ignore")
        writer.writeheader()
        writer.writerows([asdict(showtime) for showtime in showtimes])


def read_showtimes(path: pathlib.Path) -> list[Showtime]:
    """Read showtimes from CSV file, returning only those marked as interested."""
    showtimes = []
    with path.open("r") as f:
        reader = csv.DictReader(f, fieldnames=SHOWTIME_HEADERS)
        next(reader)
        for row in reader:
            showtime = Showtime(**row)
            if showtime.interested:
                showtimes.append(showtime)
    return showtimes


def select_interested_movies(
    csv_path: pathlib.Path,
    make_backup: bool = True,
    title_width: int = 35,
    desc_width: int = 80,
) -> None:
    """
    Present a TUI to choose films of interest, then update the CSV.

    Controls:
      - ↑/↓ to move
      - Space to select/deselect
      - Enter to confirm
    """
    csv_path = pathlib.Path(csv_path)
    if not csv_path.exists():
        raise FileNotFoundError(f"No CSV found at: {csv_path}")

    with csv_path.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows: list[dict[str, str]] = list(reader)
        if not rows:
            raise ValueError("CSV has no data rows.")
        fieldnames = reader.fieldnames or []

    required = {"title", "description", "interested"}
    missing = required - set(fieldnames)
    if missing:
        raise ValueError(f"CSV missing required columns: {', '.join(sorted(missing))}")

    by_title: dict[str, dict[str, object]] = {}
    for r in rows:
        title = r["title"].strip()
        desc = (r.get("description") or "").strip()
        interested_raw = (r.get("interested") or "").strip()
        interested_bool = interested_raw in {"1", "true", "True"}

        if title not in by_title:
            by_title[title] = {
                "description": desc,
                "checked": interested_bool,
            }
        else:
            by_title[title]["checked"] = bool(
                by_title[title]["checked"] or interested_bool
            )
            if desc and len(desc) > len(by_title[title]["description"]):
                by_title[title]["description"] = desc

    wrapper = textwrap.TextWrapper(width=desc_width)
    choices = []
    divider = " | "

    for title, meta in sorted(by_title.items(), key=lambda kv: kv[0].lower()):
        title_col = title[:title_width].ljust(title_width)
        desc_wrapped = wrapper.fill(meta["description"])
        desc_lines = desc_wrapped.splitlines() or [""]
        first_line = f"{title_col}{divider}{desc_lines[0]}"
        extra_lines = [
            " " * (title_width + len(divider)) + line for line in desc_lines[1:]
        ]
        label = "\n".join([first_line] + extra_lines)
        choices.append(
            questionary.Choice(title=label, value=title, checked=bool(meta["checked"]))
        )

    if not choices:
        raise ValueError("No titles found to present.")

    selected_titles: list[str] | None = questionary.checkbox(
        "Select the films you're interested in (Space to toggle, Enter to confirm):",
        choices=choices,
        validate=lambda vals: True,
        instruction="Use ↑/↓ to navigate; Space to select/deselect",
    ).ask()

    if selected_titles is None:
        print("No changes made.")
        return

    selected_set: set[str] = set(selected_titles)

    if make_backup:
        shutil.copyfile(csv_path, csv_path.with_suffix(csv_path.suffix + ".bak"))

    with csv_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for r in rows:
            title = r["title"].strip()
            r["interested"] = "1" if title in selected_set else "0"
            writer.writerow(r)

    print(f"Updated {csv_path} ({len(selected_set)} titles marked interested).")
