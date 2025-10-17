from datetime import datetime

import attrs


def convert_datetime(val: datetime | str):
    if isinstance(val, datetime):
        return val
    return datetime.fromisoformat(val)


def convert_interested(val: str | bool):
    if isinstance(val, bool):
        return val
    if isinstance(val, str):
        return bool(int(val))
    raise ValueError()


@attrs.define
class Showtime:
    id: str = attrs.field(init=False)
    title: str
    description: str
    start_dt: datetime = attrs.field(converter=convert_datetime)
    end_dt: datetime = attrs.field(converter=convert_datetime)
    theater: str
    runtime_minutes: int = attrs.field(converter=int)
    interested: bool = attrs.field(converter=convert_interested)

    def __attrs_post_init__(self):
        self.id = self.title + self.start_dt.isoformat()
