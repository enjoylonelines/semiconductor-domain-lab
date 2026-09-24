# Supervised cycle evidence: adapter-owned execution outcome

Date: 2026-09-24  
Repository/base: `/Users/hb/Projects/semiconductor-domain-lab` at `bb4997bfa46ca63d112866b029ceca3569fdfba8`

## Scope, working state, and provenance inspection

This is one isolated synthetic adapter/service experiment. No real tool, external data, infrastructure, parser format, retry policy, async lifecycle, UI, production write, or fixture acquisition was added.

Before this cycle, the working tree already contained modified `src/eda_lab/service.py`, `tests/test_stage1.py`, and untracked supervised-cycle records, `docs/evidence/2026-09-24-real-sta/`, and `docs/plans/2026-09-24-real-sta-feasibility.md`. They were inspected and preserved. The real-STA directory contains prior OpenSTA logs, execution sidecars, a manually transcribed raw-field oracle, and a boundary probe; its feasibility record says parser support is intentionally absent. None of those files was overwritten or used as an execution fixture in this cycle.

Human hypothesis and Human Prediction are `unrecorded`. Human interpretation, adoption/rejection, and Changed belief are pending human decision.

## Baseline reproduction

Focused fixture: `tests/test_stage1.py::Stage1Tests.test_adapter_process_exit_overrides_report_claimed_exit_value` writes a synthetic artifact with claimed `tool_exit_code=0` and parseable `worst_slack=0.12 ns`. Its adapter returns an `AdapterRunResult` containing the same artifact path and adapter-observed `process_exit_code=1`.

Before the service mapping change:

```sh
PYTHONPATH=src python3 -B -m unittest tests.test_stage1.Stage1Tests.test_adapter_process_exit_overrides_report_claimed_exit_value -v
```

Outcome: `FAIL`, 1 test in 0.003s. The stored run was `SUCCEEDED`, proving that service ignored the adapter-observed nonzero process outcome and trusted the parsed report claim.

## Minimal change and identical-fixture revalidation

- Added typed `AdapterRunResult(artifact_path, process_exit_code)` in `src/eda_lab/models.py`.
- `SyntheticTimingAdapter.run()` now returns that type with `process_exit_code=0`.
- `JobService` reads execution outcome solely from `AdapterRunResult.process_exit_code`; it parses only `artifact_path`.
- A nonzero process code persists attempt/run `FAILED` with `error_type=tool_exit`, while retaining parser `parse_status`, timing `check_status`, completeness, provenance, artifact path, and report raw metrics.
- The parser is unchanged. It may retain a report's claimed `tool_exit_code` as a raw artifact metric, but service no longer treats it as execution authority.
- A temporary safe bridge remains for a legacy bare path: it parses and persists artifact semantics for diagnosis but returns `FAILED` with `execution_outcome_unknown`; it never infers execution success. This preserves diagnostic behavior for existing path-only seams without claiming backwards-compatible success.

The identical focused command passed: `OK`, 1 test in 0.003s.

Relevant suite:

```sh
PYTHONPATH=src python3 -B -m unittest discover -s tests -v
```

Outcome: `OK`, 19 tests in 0.560s. Normal synthetic execution remains successful and the existing negative-slack case remains `parse_status=OK`, `check_status=FAIL`, with execution success distinct from timing failure.

## Limits and stop condition

- This proves only the isolated adapter/service state mapping. It does not validate an external process wrapper, subprocess exit capture, signal/timeout classification, actual STA parser support, real report format, retries, HTTP, or durable lifecycle behavior.
- Existing real-STA provenance/oracle evidence was not re-executed or altered; its parser acceptance remains a separate decision.
- The budget is complete: one focused baseline, one minimal contract/mapping change, one identical-fixture revalidation, and relevant-suite validation. Stop at the next Decision Gate.
