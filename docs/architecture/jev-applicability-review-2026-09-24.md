# JEV applicability review for EDA flow — 2026-09-24

## Finding

The EDA flow prototype already has the core JEV separation:

- src/eda_lab/service.py owns execution lifecycle and retry attempts.
- src/eda_lab/parser.py returns parse status separately from timing check status.
- src/eda_lab/store.py persists run status, parse status, check status, artifact path, attempts and metrics.
- docs/architecture/stage2-failure-contract.md explicitly rejects collapsing execution, parsing and check into one success flag.

The EDA flow is therefore a strong next application target for the JEV contract. It does not need a new model or a worker rewrite first.

## Applicable changes

1. Add completeness to the persisted run result.

   - complete: all required report fields and expected checks are present.
   - incomplete: the report parsed but required evidence is missing.
   - unknown: execution or parsing has not finished.

2. Add structured provenance.

   - report SHA-256
   - source kind (fixture or real)
   - tool name/version
   - flow and corner
   - parser/checker version
   - artifact path or object reference

3. Make the JEV mapping explicit in the API result:

   - job_state from execution status
   - parse_state from parse status
   - check_state from timing/BER/eye/BIST checks
   - completeness
   - provenance

4. Add acceptance tests for the important distinction:

   - tool exit succeeds, parser succeeds, timing check fails
   - tool exit succeeds, parser succeeds, required report field is missing
   - malformed report causes parse failure and never becomes a design check failure
   - fixture provenance never presents as real EDA evidence

## What should not change yet

- Keep the current adapter/parser/store boundaries.
- Do not introduce LangGraph or a second workflow state store.
- Do not claim real EDA readiness; the current tests remain synthetic.
- Do not add a generic JEV abstraction before the existing EDA result contract is made explicit.

## Recommendation

Apply the first JEV slice to Store.runs and JobService after the ontology state contract stabilizes. The smallest useful change is a backward-compatible result projection plus completeness/provenance tests. A migration to durable external workers should remain a separate decision.
