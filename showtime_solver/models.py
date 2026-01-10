"""
Data models for the showtime solver.
"""

from dataclasses import dataclass, field
from datetime import datetime


@dataclass(frozen=True)
class Showtime:
    """A single movie showing at a specific theater and time."""

    title: str
    description: str
    start_dt: datetime
    end_dt: datetime
    theater: str
    runtime_minutes: int
    interested: bool
    id: str = field(init=False, compare=False, hash=False)

    def __post_init__(self):
        """Generate a unique ID and convert string inputs to proper types."""
        # Convert string inputs to proper types if needed (using object.__setattr__ for frozen dataclass)
        if isinstance(self.start_dt, str):
            object.__setattr__(self, "start_dt", datetime.fromisoformat(self.start_dt))
        if isinstance(self.end_dt, str):
            object.__setattr__(self, "end_dt", datetime.fromisoformat(self.end_dt))
        if isinstance(self.runtime_minutes, str):
            object.__setattr__(self, "runtime_minutes", int(self.runtime_minutes))
        if isinstance(self.interested, str):
            object.__setattr__(self, "interested", bool(int(self.interested)))

        # Create unique ID from title and start time
        object.__setattr__(self, "id", self.title + self.start_dt.isoformat())
