# Supervisor scope-conflict review

Date: 2026-09-24  
Repository: `/Users/hb/Projects/semiconductor-domain-lab`  
Observed branch / HEAD: `main` / `bb4997bfa46ca63d112866b029ceca3569fdfba8`

## Checkpoint

- Diff summary: five modified product/test files; OpenSTA evidence, plans, decision records, focused test, and lockfile are untracked. Nothing is staged.
- Tests run in this review: none. This is an inspection-only checkpoint; earlier evidence records their own results.
- Experiment / result: prior bounded state-mapping and actual OpenSTA setup/max parser slices report completion; async lifecycle, PostgreSQL, Redis, and deployment were not executed here.
- Evidence: `docs/evidence/2026-09-24-supervised-cycle.md`, `docs/evidence/2026-09-24-supervised-execution-contract-cycle.md`, and `docs/evidence/2026-09-24-real-sta/implementation-result.md`.

## Alignment and conflicts

- Aligned: execution, parse, and check state remain separate; the bounded OpenSTA fixture distinguishes actual tool output from synthetic data; production/subprocess claims remain excluded.
- Aligned: Kafka is not a default component. Existing scope opens broker alternatives only after an observed lifecycle failure and a same-workload comparison.
- Missing before Kafka could be considered: the plans do not yet define measurable triggers for retained replay, independent consumers, durable reprocessing, ordering, or throughput/backpressure. Redis Pub/Sub and a PostgreSQL source-of-truth path are likewise requested future scope, not current evidence.
- Conflict: README and older supervised-cycle records describe a synthetic-only, pre-actual-fixture state, while the newer OpenSTA implementation record says the bounded real-fixture parser slice is complete. The scope-depth review also names the already-completed false-success correction as the next task.
- Conflict: the pasted target vertical slice names PostgreSQL, Redis, worker, and API. The repository's current bounded scope explicitly excludes new DB/broker infrastructure until parser correctness and a measured async failure justify it. Treat those items as conditional phases, not immediate implementation.

## Unresolved question and decision required

The user owns whether the bounded actual-report/parser closure is sufficient to open exactly one async lifecycle experiment. Before any broker decision, choose a lifecycle failure mode and define the workload, invariant, baseline, smallest alternative, and explicit Kafka trigger criteria.

## Stop condition

No implementation, test rerun, infrastructure change, or Career OS update was performed. Stop at this supervisor checkpoint.
