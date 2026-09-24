# Supervised decision record: adapter-owned execution outcome

Date: 2026-09-24  
Evidence: `docs/evidence/2026-09-24-supervised-execution-contract-cycle.md`  
Base commit: `bb4997bfa46ca63d112866b029ceca3569fdfba8`

## Options

1. **Adopt the typed adapter-result contract.** `AdapterRunResult.process_exit_code` is the sole execution-success authority; parsed report fields remain artifact semantics. Keep the safe bare-path bridge as a fail-closed diagnostic boundary until every JobService adapter returns the typed result.
2. **Adopt the contract but remove the bridge.** Require typed results immediately; legacy path-only adapters fail at the type boundary rather than producing parse diagnostics.
3. **Reject/revise the contract.** Supply an explicit alternative ownership contract for process exit and artifact reporting. Do not restore parser-emitted exit fields as execution authority without new evidence and a distinct experiment.

## Human-owned fields

- Human hypothesis: unrecorded.
- Human Prediction: unrecorded.
- Human interpretation: pending human decision.
- Adoption/rejection and accepted trade-off: pending human decision.
- Changed belief: pending human decision.

## Stop status

The authorized one-question experiment is complete. No adapter-specific external-process integration, real fixture/parser change, or additional lifecycle work follows automatically.
