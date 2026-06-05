"""CronJob dataclass for the cron scheduler."""

from __future__ import annotations

import time
from dataclasses import dataclass, field, asdict


@dataclass
class CronJob:
    id: str
    cron: str
    prompt: str
    recurring: bool = True
    durable: bool = True
    enabled: bool = True
    last_fired: float | None = None
    last_fired_minute: str | None = None  # "YYYY-MM-DD HH:MM" — prevents double-fire
    created_at: float = field(default_factory=time.time)

    def to_dict(self) -> dict:
        d = asdict(self)
        return d

    @classmethod
    def from_dict(cls, d: dict) -> CronJob:
        return cls(**{k: v for k, v in d.items() if k in cls.__dataclass_fields__})
