# Stage 1 Architecture Decision

## Decision
Use a dependency-light Python prototype with SQLite, an in-process bounded worker pool, a synthetic EDA adapter, and a standard-library HTTP API. Keep adapter, parser, storage, and orchestration boundaries explicit so later stages can replace one piece without pretending to support real EDA.

## Why
The first acceptance target is one complete job path: submit → queue → synthetic execution → artifact collection → parsing → Run/Artifact/Metric persistence → status/result query. A full web framework, broker, object store, and vendor EDA tool would add setup cost before the domain boundary is tested.

## Alternatives rejected
- Directly invoking a proprietary EDA tool: no licensed tool or stable format is available.
- Supporting multiple IPs first: would hide whether the base job and artifact contract is sound.
- Kubernetes or autoscaling first: resource policy cannot be evaluated before job duration, artifact size, and failure behavior are measured.
- Treating parser success as design pass: execution, parsing, and check status remain separate.

## Domain-derived problem hypothesis
Public role descriptions motivate a need for repeatable visibility over design and verification work: what was requested, what ran, which artifacts were produced, what was parsed, and which checks require engineering judgment. This is an inferred workflow hypothesis, not an observed internal-company bottleneck or a measured user benefit. See the [canonical scope and stop contract](../plans/research-and-scope-2026-09-23.md).

## Stage boundaries
Stages describe separate evidence scopes, not an automatic implementation backlog. Stop when the selected synthetic contract is demonstrated; real integration requires new evidence and a separate scope decision. A worker-count limit does not establish bounded admission or durable queue behavior.

1. Functional vertical slice: one synthetic timing flow.
2. Reliability: failure, retry, cancellation, idempotency, structured events.
3. Bounded load: explicit concurrent-job and artifact assumptions; measure latency and queue behavior.
4. Real integration assessment: map the adapter contract to an actual EDA command, license policy, artifact retention, and resource quota. Do not claim production readiness without those inputs.

## Initial state model
Job state: QUEUED → RUNNING → SUCCEEDED | FAILED | CANCELLED.
Parse state: NOT_STARTED → OK | PARTIAL | INVALID.
Check state: UNKNOWN | PASS | FAIL.
A SUCCEEDED job may have a FAIL check.
