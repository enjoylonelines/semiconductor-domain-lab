# Supervised P0 cycle decision record

Date: 2026-09-24  
Evidence: `docs/evidence/2026-09-24-supervised-cycle.md`  
Base commit: `bb4997bfa46ca63d112866b029ceca3569fdfba8`

## Decision options

1. **Adopt the bounded mapping correction.** Treat nonzero parsed `tool_exit_code` as execution failure while retaining parse/check/provenance/raw-metric detail. Evidence: the focused synthetic regression changed from false `SUCCEEDED` to `FAILED`, and 18 relevant tests pass.
2. **Reject or revise the mapping correction.** Revert or alter the policy only with a different explicit execution-state contract; the current experiment does not justify retrying tool exits, treating positive slack as success, or combining execution/parse/check axes.
3. **Authorize the actual STA fixture gate.** Supply or approve acquisition of one traceable authorized public/real report meeting the acceptance gate in the evidence record, then separately compare independent raw fields and normalized output.
4. **Stop this slice without fixture acquisition.** Keep the correction as bounded synthetic evidence only and explicitly leave authentic STA provenance/oracle closure unmet.

## Human-owned fields

- Human hypothesis: unrecorded.
- Human Prediction: unrecorded.
- Human interpretation: pending human decision.
- Adoption/rejection: pending human decision.
- Changed belief: pending human decision.
- Selected option and trade-off acceptance: pending human decision.

## Stop status

The assigned one-question experiment budget is complete. No further implementation is authorized by this record; stop at the Decision Gate.
