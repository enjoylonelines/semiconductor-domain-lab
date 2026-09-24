# Supervised P0 cycle: execution-state false success and STA fixture gate

Date: 2026-09-24  
Repository/base: `/Users/hb/Projects/semiconductor-domain-lab` at `bb4997bfa46ca63d112866b029ceca3569fdfba8`

## Problem framing

- **Problem:** Determine whether an EDA run with a nonzero `tool_exit_code` and parseable slack can be persisted as `SUCCEEDED`; if reproduced, prevent that execution-state false success without changing parser formats. Then determine whether an authentic STA report fixture and an independent raw-field oracle already exist in this checkout.
- **Human hypothesis:** unrecorded.
- **Human Prediction:** unrecorded.
- **AI prediction (separate):** the service currently derives persisted success from parse/check results without making nonzero tool exit terminally unsuccessful; a focused regression can pin this and a condition at the execution-to-state mapping boundary can prevent it.
- **Falsification condition:** If a focused fixture with nonzero exit plus parseable finite slack does not persist `SUCCEEDED`, do not change execution-state mapping for this asserted bug. If the smallest change breaks the existing success/parse/check distinctions, reject it. If no traceable authentic STA report fixture exists, do not fabricate one or broaden parsing; record the acceptance gate only.
- **Experiment budget:** one focused baseline reproduction; at most one minimal mapping reinforcement; one identical-fixture revalidation; then provenance/oracle inspection only. No async lifecycle, hardware, UI, scheduler, format expansion, new infrastructure, paid/external runs, production writes, commit, or push.
- **Invariant:** execution failure, parser result, and timing/check result remain separately observable; nonzero execution status must not be persisted as `SUCCEEDED`; a zero-exit valid fixture retains its existing successful behavior.
- **STOP / Decision required:** Stop after the revalidation and fixture gate. A human must decide whether the documented provenance gate is sufficient to accept this P0 slice or authorize obtaining/adding a traceable public authentic STA fixture.
- **Unknowns:** the exact current state-mapping branch; whether existing fixture files are authentic STA reports versus synthetic references; whether an independent raw-field oracle exists.

## Alternatives

- **Baseline:** preserve current mapping and demonstrate the alleged false-success fixture, if it exists.
- **Challenger:** reject nonzero tool exit at the smallest execution-state mapping boundary while retaining parsed/check detail.
- **Not selected:** parser-format changes, a new STA fixture, async/retry changes, or a combined success flag. These exceed the bounded question or erase the required state separation.

## Discriminating experiment

- **Fixture/workload:** a deterministic isolated test double returning nonzero exit and parseable finite slack, followed by the identical fixture after the one permitted reinforcement.
- **Metrics:** persisted state; stored tool exit/parse/check fields; focused regression outcomes.
- **Adoption/rejection gate:** adopt only if baseline demonstrates persisted `SUCCEEDED` and challenger makes the same fixture non-success while relevant existing tests pass. Otherwise leave product mapping unchanged and document the result.

## Implementation and outcome

- Implementation is conditional on the baseline reproduction.
- Evidence: `docs/evidence/2026-09-24-supervised-cycle.md`.
- Decision record: `docs/decisions/2026-09-24-supervised-cycle.md`.
- Human decision: pending human decision.
- Changed belief: pending human decision.
