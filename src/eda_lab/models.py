from dataclasses import dataclass
from typing import Any

@dataclass(frozen=True)
class JobSpec:
    job_id: str
    design_id: str
    ip_family: str
    flow_name: str
    corner: str
    worst_slack: float
    unit: str
    duration_seconds: float = 0.02

@dataclass(frozen=True)
class ParseResult:
    parse_status: str
    check_status: str
    metrics: dict[str, Any]
    errors: list[str]
