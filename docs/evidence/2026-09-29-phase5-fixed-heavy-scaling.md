# Fixed Heavy workload scaling evidence

## Contract

Eight calibrated Heavy OpenSTA Runs were held fixed while the Host Agent dispatch cap and independent Supervisor count changed together. Environment: one 8-CPU, 20-GiB Colima Linux VM; PostgreSQL 16; each Supervisor capped at 1 CPU and 2 GiB. This validates same-VM container concurrency, not multi-machine scaling.

## Results

| Supervisors | repetitions | p50 makespan | p95 makespan | accepted completion |
| ---: | ---: | ---: | ---: | --- |
| 1 | 1 | 75.94s | not measured | 8/8 TRUSTED |
| 2 | 3 | 40.40s | 40.67s | 24/24 TRUSTED |
| 4 | 3 | 21.40s | 21.41s | 24/24 TRUSTED |
| 8 | 3 | 12.08s | 12.32s | 24/24 TRUSTED |

The 2/4/8 samples observed PostgreSQL lock wait maximum 0. Maximum database connections were 5, 7, and 11. Supervisor CPU peaks were approximately 100% of each one-CPU cap; peak memory per Supervisor was 1,159--1,228 MiB, below the 2-GiB cap.

## Decision and limit

For this workload and VM, execution CPU is saturated while PostgreSQL lock wait is absent. The fixed eight-Run makespan continues to decrease through eight Supervisors, so the predeclared scaling-limit trigger has not fired and Kafka is not justified. One-Supervisor has one valid corrected regression only; it is not a p95 sample. No claim is made about physical multi-host throughput, production capacity, or a Kafka comparison.
