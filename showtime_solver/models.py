"""
Data models for the showtime solver.
"""

from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class Showtime:
    """A single movie showing at a specific theater and time."""

    title: str
    description: str
    start_dt: datetime
    end_dt: datetime
    theater: str
    runtime_minutes: int
    interested: bool
    id: str = field(init=False)

    def __post_init__(self):
        """Generate a unique ID for this showtime."""
        # Convert string inputs to proper types if needed
        if isinstance(self.start_dt, str):
            self.start_dt = datetime.fromisoformat(self.start_dt)
        if isinstance(self.end_dt, str):
            self.end_dt = datetime.fromisoformat(self.end_dt)
        if isinstance(self.runtime_minutes, str):
            self.runtime_minutes = int(self.runtime_minutes)
        if isinstance(self.interested, str):
            self.interested = bool(int(self.interested))

        # Create unique ID from title and start time
        self.id = self.title + self.start_dt.isoformat()
