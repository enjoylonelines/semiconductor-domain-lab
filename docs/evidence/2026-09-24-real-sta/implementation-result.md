# OpenSTA setup/max parser implementation result

작성일: 2026-09-24  
기준: 실제 OpenSTA raw report fixture [normal.log](normal.log), [tight.log](tight.log).

## Implemented

`parse_report` now dispatches the existing synthetic format and a bounded OpenSTA format. The supported OpenSTA profile is exactly:

- OpenSTA 3.1.0 banner
- one max/setup timing path
- report_units time 1ns
- one startpoint, endpoint, path group and worst slack summary
- EDA_LAB_REPORT_END marker emitted by the recorded Tcl profile

The parser stores tool-generated provenance rather than synthetic provenance, including raw SHA256, tool revision, analysis type, report profile and normalized path fields. It validates the summary arithmetic using the signed closing arrival summary printed by OpenSTA and preserves the positive path arrival time as its normalized metric.

## Validation

```sh
PYTHONPATH=src .venv/bin/python -m unittest tests/test_opensta_report.py -v
PYTHONPATH=src .venv/bin/python -m unittest discover -s tests -v
```

Results: 7 OpenSTA-focused tests passed; full suite passed 26 tests. The full suite printed pre-existing SQLite ResourceWarnings during the bounded batch test but completed successfully.

The tests establish:

- normal report: parse OK / check PASS / +9.459949ns
- tight report: parse OK / check FAIL / -0.440050ns
- tight report with process exit 0: run SUCCEEDED, check FAIL
- normal report with observed process exit 17: run FAILED, parse OK, check PASS
- missing marker, unsupported OpenSTA version, OpenSTA diagnostic, and inconsistent worst slack: INVALID / UNKNOWN

## Limitation

The service integration uses a replay adapter returning the preserved raw report and a recorded process exit. The parser and state boundary are exercised, but a production subprocess adapter that invokes OpenSTA from user-supplied inputs is deliberately outside this slice.
