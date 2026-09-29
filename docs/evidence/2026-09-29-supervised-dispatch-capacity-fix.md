# Supervised dispatch capacity fix

## Failure

A fixed batch of eight Heavy Runs with one Supervisor initially produced three `SUCCEEDED/TRUSTED` results followed by five `FAILED/UNKNOWN` results. The Supervisor exited with `supervisor finalization lost its lease fence`; it was not OOM-killed.

## Root cause

The Host Agent claimed and leased all queued Runs immediately. In supervised mode its futures returned once requests were enqueued, so `max_in_flight` did not bound durable execution requests. A single Supervisor then reached later requests after their 30-second Attempt leases had expired.

## Change

`PostgresWorker` now counts host-local execution requests in `QUEUED`, `CLAIMED`, or `RUNNING` state before claiming another supervised Run. It stops dispatching when that count reaches `max_in_flight`. This aligns leased work with configured execution capacity instead of using enqueue completion as capacity evidence.

## Regression evidence

With one Supervisor and fixed eight calibrated Heavy Runs, the rerun completed in 75.935453 seconds: 8/8 `SUCCEEDED/TRUSTED`, 0 `FAILED/UNKNOWN`. This validates the corrected one-Supervisor baseline only. Worker 2/4/8 repeated resource and PostgreSQL measurements remain pending.
