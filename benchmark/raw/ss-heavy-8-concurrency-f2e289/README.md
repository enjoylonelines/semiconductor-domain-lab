# Rejected setup record

`rejected-missing-heavy-runtime-config.json` records the initial 8-way batch
that omitted `EDA_OPENSTA_SCRIPT_NAME` and `EDA_OPENSTA_NETLIST_PATH`. It
executed the default tiny fixture and is excluded from SS Heavy conclusions.

`heavy-input-preflight.json` verifies the repaired input contract. `summary.json`
contains the three measured 8-way SS Heavy batches. `timing-reports/` and its
manifest preserve the 24 terminal reports accepted by those measured batches.
