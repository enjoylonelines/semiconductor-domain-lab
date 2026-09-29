# MCMM input acquisition plan

## Purpose

Extend the bounded OpenSTA Heavy workload only with characterized SKY130 HD inputs. Repository code and current single-corner evidence remain authoritative; Career OS receives only a link or summary.

## Selected conditions

| scene | Liberty input | source of condition | status |
| --- | --- | --- | --- |
| TT functional | `sky130_fd_sc_hd__tt_025C_1v80.lib` | existing pinned fixture | available |
| FF functional | `sky130_fd_sc_hd__ff_n40C_1v95.lib` | OpenLane/OpenPDK configuration | acquisition required |
| SS functional | `sky130_fd_sc_hd__ss_100C_1v60.lib` | OpenLane/OpenPDK configuration | acquisition required |
| tight constraint | existing `tight.sdc` | stress constraint only | available, not a functional mode |

This is PVT-corner comparison, not full MCMM sign-off. A scan mode requires scan-aware netlist and SDC. Parasitic scenes require an extracted SPEF from a physical implementation; neither input currently exists.

## Provenance gate

Before execution, record the PDK distribution, immutable revision, source URL, SHA-256 for every assembled Liberty file, and OpenSTA parser acceptance. Do not use a third-party copied `.lib` or fabricate a SPEF.

## Current acquisition evidence

The official SkyWater HD source repository was inspected at `ac7fb61f06e6470b94e8afdf7c25268f62fbd7b1`. It contains per-cell Liberty JSON but no assembled FF/SS `.lib`. A temporary Volare fetch attempt for a pinned SKY130 artifact did not create a PDK store, so it is not an available input and no MCMM run is claimed.

## Human Decision Gate

Proceed only after an official OpenPDK/Volare artifact fetch is reproducible and the three assembled Liberty hashes are recorded. Otherwise retain the current result as single-corner OpenSTA execution evidence.
