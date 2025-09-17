from datetime import datetime
from pydantic import BaseModel
from app.models.enums import InstanceStatus

class StatusEventOut(BaseModel):
    id: int
    changed_at: datetime
    from_status: str | None
    to_status: str
    class Config:
        from_attributes = True

class StatusSegmentOut(BaseModel):
    start: datetime
    end: datetime
    status: InstanceStatus
    seconds: int

class StatusStatsOut(BaseModel):
    window_start: datetime
    window_end: datetime
    total_seconds: int
    seconds_by_status: dict[str, int]
    uptime_seconds: int
    uptime_percent: float
    segments: list[StatusSegmentOut] | None = None
