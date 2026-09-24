# Supervised cycle: adapter-owned execution outcome

Date: 2026-09-24  
Repository/base: `/Users/hb/Projects/semiconductor-domain-lab` at `bb4997bfa46ca63d112866b029ceca3569fdfba8`

## Problem framing

- **Observed problem:** The existing service uses parser-emitted `metrics.tool_exit_code` to decide whether an execution succeeded. An artifact field is report semantics and can disagree with the adapter-observed process outcome.
- **Human hypothesis:** unrecorded.
- **Human Prediction:** unrecorded.
- **AI prediction (separate):** with an adapter result that carries `artifact_path` and `process_exit_code`, a fixture whose report claims zero exit but whose adapter returns nonzero will demonstrate that the current path can succeed falsely; mapping from the typed result will reject it while retaining parser output.
- **Falsification condition:** If the focused disagreement fixture is already rejected without reading the parsed report exit field, or if the smallest adapter-result change cannot preserve parse/check/provenance/raw metrics and existing normal/negative-slack behavior, do not adopt this contract.
- **Experiment budget:** one focused baseline; one typed adapter-result mapping change; one identical-fixture revalidation; focused and relevant existing tests only. No real tool/fixture/format/retry/async/UI/external-data/infrastructure work and no edits to pre-existing `docs/evidence/2026-09-24-real-sta/` or its feasibility plan.
- **Invariant:** only adapter-observed `process_exit_code` controls execution success; parser stays artifact semantics only; parser status, check status, provenance, artifact path, and raw metrics remain stored; a report-claimed exit value cannot override a nonzero process exit.
- **STOP / Decision required:** Stop after validation. A human must decide whether to adopt the typed adapter-result contract and, separately, whether to authorize adapter-specific process/error integration for actual tools.
- **Unknowns:** external adapter error classification and process lifecycle behavior are outside this cycle; existing evidence probes that return bare paths are not upgraded unless needed for a safe contract bridge.

## Alternatives

- **Baseline:** service treats parsed `tool_exit_code` as execution authority.
- **Challenger:** `AdapterRunResult(artifact_path, process_exit_code)` makes the service map execution state before artifact interpretation.
- **Not selected:** parsing a new field/format, trusting provenance as an exit source, adding retry rules, or adding a legacy bare-path compatibility success path. A bare path has no trustworthy process outcome.

## Discriminating experiment

- **Fixture/workload:** deterministic synthetic report claims `tool_exit_code=0` and finite positive slack; its adapter result reports `process_exit_code=1`.
- **Metrics:** persisted run/attempt state and error type; persisted parse/check/provenance/raw report metric; focused test outcome.
- **Adoption/rejection gate:** adopt only if baseline falsely persists `SUCCEEDED`, the identical fixture then persists `FAILED/tool_exit`, and relevant existing tests preserve normal and check-failure behavior.

## Outcome

- Evidence: `docs/evidence/2026-09-24-supervised-execution-contract-cycle.md`.
- Decision record: `docs/decisions/2026-09-24-supervised-execution-contract-cycle.md`.
- Human interpretation, adoption/rejection, and Changed belief: pending human decision.
