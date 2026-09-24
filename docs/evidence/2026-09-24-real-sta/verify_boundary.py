"""Bounded evidence probe; no product changes or persistent database writes."""
import dataclasses, hashlib, json, math, re
from pathlib import Path
from eda_lab.parser import parse_report
from eda_lab.models import JobSpec
from eda_lab.service import JobService
from eda_lab.store import Store

base = Path(__file__).resolve().parent
out = {}
# Manually transcribed oracle from raw report rows, not from production parser.
expected = {
    "normal": (9.883325, 0.423375, 9.459949, "MET"),
    "tight": (-0.016675, 0.423375, -0.440050, "VIOLATED"),
}
for name, (required, arrival, slack, label) in expected.items():
    path = base / (name + ".log")
    raw = path.read_text()
    assert " time 1ns" in raw and "Path Type: max" in raw
    assert "Startpoint: _3_" in raw and "Endpoint: _2_" in raw
    assert raw.rstrip().endswith("EDA_LAB_REPORT_END")
    observed = float(re.search(r"([-\d.]+)\s+slack \(" + label + r"\)", raw)[1])
    summary = float(re.search(r"worst slack max ([-\d.]+)", raw)[1])
    assert math.isfinite(observed) and abs(observed - slack) < 1e-9
    assert abs(required - arrival - observed) <= 0.000002
    assert summary == observed
    parsed = parse_report(path)
    assert parsed.parse_status == "INVALID" and parsed.check_status == "UNKNOWN"
    class Replay:
        def run(self, spec):
            return path
    service = JobService(store=Store(), adapter=Replay(), max_workers=1, max_attempts=1)
    service.submit(JobSpec(name, "tiny", "research", "sta_setup", "tt_025C_1v80", 0, "ns"))
    service.executor.shutdown(wait=True)
    run = service.get(name)
    assert run["status"] == "FAILED" and run["parse_status"] == "INVALID"
    assert run["check_status"] == "UNKNOWN"
    out[name] = dict(manual_oracle=dict(required_ns=required, arrival_ns=arrival,
        slack_ns=slack, arithmetic_tolerance_ns=0.000002),
        parse_result=dataclasses.asdict(parsed), stored_run=run)
print(json.dumps(out, indent=2))
