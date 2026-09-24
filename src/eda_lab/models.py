from dataclasses import dataclass
from pathlib import Path
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
    completeness: str = "unknown"
    provenance: dict[str, Any] | None = None
    semantic_status: str = "UNKNOWN"
    provenance_status: str = "UNKNOWN"


@dataclass(frozen=True)
class AdapterRunResult:
    """Adapter-observed execution outcome and its emitted artifact."""

    artifact_path: Path
    process_exit_code: int | None
    execution_provenance: dict[str, Any] | None = None
