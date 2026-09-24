# P1 async lifecycle and recovery evidence

Plan: [async lifecycle and recovery cycle](../plans/2026-09-24-async-lifecycle-recovery-cycle.md).

## Baseline

The pre-change service was run with its real `SyntheticTimingAdapter`, while `parse_report` was replaced only for this probe with `SystemExit` after `adapter.run()` returned its artifact. The future raised `SystemExit`; the durable read was:

```json
{"future_error":{"message":"simulated worker interruption after artifact return","type":"SystemExit"},"persisted":{"artifact_path":null,"attempts":[],"check_status":"UNKNOWN","completeness":"unknown","error":null,"job_id":"crash-window-baseline","metrics":null,"parse_status":"NOT_STARTED","status":"RUNNING"}}
```

This is an in-process interruption injection, not a killed OS process or a real EDA subprocess crash. It demonstrates the selected durability gap only: an emitted artifact can be followed by a missing attempt record and an unresolved durable run.

## Revalidation

`PYTHONPATH=src .venv/bin/python -m unittest discover -s tests -v` completed successfully: **30 tests** in 0.218 s.

Focused cases:

| Case | Observed durable result |
| --- | --- |
| first timeout then normal adapter result | attempt 1 `RETRYABLE_FAILURE/retryable`, attempt 2 `SUCCEEDED/not_applicable`, run `SUCCEEDED` |
| valid artifact with observed process exit 9 | one attempt `FAILED/non_retryable`, run `FAILED`; `max_attempts=2` did not cause a second attempt |
| injected `SystemExit` after artifact return | initial attempt remains `RUNNING/not_classified`; `recover_stale_runs(0)` after the future ended records `ABANDONED/worker_unavailable/recovery_required` and run `FAILED` |
| old `RUNNING` database timestamp with a blocked live local future | recovery reports `skipped_live`; run and attempt remain `RUNNING` until that future completes |

The prior parser/check separation tests also passed: a timing violation can retain successful execution while `check_status=FAIL`, and a nonzero observed tool exit remains failed even with a valid report.

## Limits

No external worker, child PID, OS signal, real tool subprocess, clock source, or cross-process restart was tested. `recover_stale_runs` knows only this `JobService` instance's futures; after a real process restart it can mark a stale record failed, but cannot prove whether an external child is still alive. It does not retry recovered work. No latency, throughput, retention, replay, or multi-consumer evidence was collected.
