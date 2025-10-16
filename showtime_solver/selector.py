import csv
import pathlib
import shutil
import sys
import textwrap
from datetime import datetime, timedelta

import questionary
import requests
from bs4 import BeautifulSoup

URL = "https://filmadelphia.org/festival/films/"
HTML_FILE = pathlib.Path("program.html")
SHOWTIME_FILE = pathlib.Path("showtimes.csv")
FESTIVAL_YEAR = 2025


def fetch_program(url: str) -> str:
    """Fetch HTML content from a URL and save it locally."""
    print(f"Fetching HTML from {url} ...", file=sys.stderr)
    response = requests.get(url, timeout=15)
    response.raise_for_status()
    html = response.text
    return html


def load_program() -> str:
    """Load HTML from file if it exists, otherwise fetch it."""
    if not HTML_FILE.exists():
        program_html = fetch_program(URL)
        HTML_FILE.write_text(program_html)
        print(f"Saved HTML to {HTML_FILE}", file=sys.stderr)
    else:
        print(f"Using cached HTML from {HTML_FILE}", file=sys.stderr)

    return HTML_FILE.read_text()


def parse_program(html: str) -> set[tuple]:
    """Extract movie showtimes from the HTML.

    There's a parsing bug somewhere in here, where it double-writes each showtime, but
    I just throw everything into a set since we're not dealing with a ton of data.
    """
    soup = BeautifulSoup(html, "html.parser")
    shows = set()

    for movie in soup.select(".movie-tags"):
        # Get movie title
        title_tag = movie.select_one(".text-xl.font-bold a")
        title = title_tag.get_text(strip=True) if title_tag else "N/A"

        # Get movie description
        description_tag = title_tag.parent.find_next_sibling()
        description = description_tag.get_text(strip=True)

        # get movie runtime (minutes)
        runtime_el = movie.find("span", string=lambda s: s and "Runtime" in s)
        if runtime_el:
            parent = runtime_el.find_parent()
            if parent:
                runtime_minutes = int(
                    parent.get_text(strip=True)
                    .replace("Runtime:", "")
                    .replace("min", "")
                    .strip()
                )

        showtime_blocks = movie.select(
            ".flex-wrap.mt-4.md\\:flex, .flex-wrap.-mt-2.md\\:hidden"
        )

        for block in showtime_blocks:
            date = None
            theater = None
            for el in block.find_all(["div", "a"], recursive=False):
                if el.name == "div":
                    text = el.get_text(strip=True)
                    if "," in text:  # e.g. "Sat, Oct 18"
                        date = text
                    elif "Film Society" in text:
                        theater = text
                elif el.name == "a" and "button-showtime" in el.get("class", []):
                    time = el.get_text(strip=True)
                    if date and time and theater:
                        start_dt = datetime.strptime(
                            f"{f'{date} {time}'};{FESTIVAL_YEAR}",
                            "%a, %b %d %I:%M%p;%Y",
                        )
                        end_dt = start_dt + timedelta(minutes=runtime_minutes)
                        row = (
                            title,
                            description,
                            start_dt,
                            end_dt,
                            theater,
                            runtime_minutes,
                            0,  # not interested
                        )
                        shows.add(row)

    return shows


SHOWTIME_HEADERS = [
    "title",
    "description",
    "start_dt",
    "end_dt",
    "theater",
    "runtime_minutes",
    "interested",
]


def write_showtimes(showtimes):
    SHOWTIME_FILE.touch()
    with SHOWTIME_FILE.open("w") as f:
        writer = csv.writer(f)
        writer.writerow(SHOWTIME_HEADERS)
        writer.writerows(showtimes)


def parse_showtime_csv_row(row):
    return {
        "title": row["title"],
        "description": row["description"],
        "start_dt": datetime.fromisoformat(row["start_dt"]),
        "end_dt": datetime.fromisoformat(row["end_dt"]),
        "theater": row["theater"],
        "runtime_minutes": row["runtime_minutes"],
        "interested": int(row["interested"]),
    }


def read_showtimes(path: pathlib.Path):
    showtimes = []
    with path.open("r") as f:
        reader = csv.DictReader(f, fieldnames=SHOWTIME_HEADERS)
        next(reader)
        for row in reader:
            showtime = parse_showtime_csv_row(row)
            if showtime["interested"]:
                showtimes.append(showtime)
    return showtimes


def select_interested_movies(
    csv_path: pathlib.Path,
    make_backup: bool = True,
    title_width: int = 35,
    desc_width: int = 80,
) -> None:
    """
    Read a festival CSV, present a TUI to choose films of interest (deduped by title),
    in a two-column view (title | description), then write the updated 'interested' values
    (1/0) back to the CSV for all showtimes of each selected title.

    Controls:
      - ↑/↓ to move
      - Space to select/deselect
      - Enter to confirm
    """
    csv_path = pathlib.Path(csv_path)
    if not csv_path.exists():
        raise FileNotFoundError(f"No CSV found at: {csv_path}")

    # --- Load rows -----------------------------------------------------------
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

    # --- Deduplicate by title ------------------------------------------------
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
            # Combine interest flags and keep longest description if duplicates
            by_title[title]["checked"] = bool(
                by_title[title]["checked"] or interested_bool
            )
            if desc and len(desc) > len(by_title[title]["description"]):
                by_title[title]["description"] = desc

    # --- Prepare two-column labels ------------------------------------------
    wrapper = textwrap.TextWrapper(width=desc_width)
    choices = []
    divider = " | "

    for title, meta in sorted(by_title.items(), key=lambda kv: kv[0].lower()):
        # Left column: fixed width title, truncated if too long
        title_col = title[:title_width].ljust(title_width)
        # Right column: wrapped description
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

    # --- Prompt --------------------------------------------------------------
    if not choices:
        raise ValueError("No titles found to present.")

    selected_titles: list[str] = questionary.checkbox(
        "Select the films you're interested in (Space to toggle, Enter to confirm):",
        choices=choices,
        validate=lambda vals: True,
        instruction="Use ↑/↓ to navigate; Space to select/deselect",
    ).ask()

    if selected_titles is None:
        print("No changes made.")
        return set()

    selected_set: set[str] = set(selected_titles)

    # --- Write updates back --------------------------------------------------
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
