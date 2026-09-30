# Multi-host compute scaling and Redis progress evidence

Date: 2026-09-30
Base revision: `db4967e`

## Scope

This cycle closes the JD-facing execution slice after PostgreSQL coordination profiling.

Goals:

1. verify that the supervised EDA architecture can use additional execution compute across two logical Host identities;
2. capture container-operational evidence and the next scaling limit;
3. add Redis Pub/Sub only for ephemeral progress delivery while PostgreSQL remains authoritative.

This is **not** physical multi-host proof. All containers share the same Docker VM.

## 1. Fixed SS Heavy workload

The same calibrated SS Heavy PicoRV32 x64 workload and provenance were used:

- Liberty SHA-256: `9b24f0db3967ac67b4cae1f74bb480fd47922d18d0ed577e3c121739b412c361`
- Netlist SHA-256: `b3f09a42b23a9ff84c0084d4d284a9f8f5830b4c50f4972d68f59a18ea0938ce`
- Script SHA-256: `cad5237c39e914222b23d6f30a86c6c34d5782bad5480dc7c8714607fb2688a1`

Container budgets:

- PostgreSQL: 0.5 CPU / 384 MiB
- each Supervisor: 1 CPU / 1.5 GiB
- Docker VM compute budget: 8 CPUs
- Host Agent dispatch budget: 4 requests per logical Host

## 2. 4-slot baseline

Profile:

```text
1 logical Host
  └ 4 Supervisors × 1 CPU
```

16 SS Heavy Runs, three repeats:

| repeat | elapsed | throughput | host distribution |
| ---: | ---: | ---: | --- |
| 1 | 40.26 s | 0.397 Runs/s | 16 |
| 2 | 40.42 s | 0.396 Runs/s | 16 |
| 3 | 40.59 s | 0.394 Runs/s | 16 |

Median:

- elapsed: **40.42 s**
- throughput: **0.396 Runs/s**

All 48 Runs were `SUCCEEDED/TRUSTED`.

## 3. 8-slot logical multi-host profile

Profile:

```text
logical Host B1                logical Host B2
  └ 4 Supervisors × 1 CPU       └ 4 Supervisors × 1 CPU
              \                  /
               \                /
                shared PostgreSQL
```

16 SS Heavy Runs, three repeats:

| repeat | elapsed | throughput | Host B1 : B2 |
| ---: | ---: | ---: | ---: |
| 1 | 32.21 s | 0.497 Runs/s | 9 : 7 |
| 2 | 23.57 s | 0.679 Runs/s | 8 : 8 |
| 3 | 33.79 s | 0.474 Runs/s | 6 : 10 |

Median:

- elapsed: **32.21 s**
- throughput: **0.497 Runs/s**

Relative to the 4-slot median:

- throughput: **+25.5%**
- elapsed time: **-20.3%**

When the two logical Hosts received an even 8:8 split, throughput reached **0.679 Runs/s**, about **+71.5%** over the 4-slot median.

All 48 Runs were `SUCCEEDED/TRUSTED`, all execution requests reached `COMPLETED`, no expired live Attempt was observed, and provenance remained uniform.

## 4. Longer 32-Run observation

The 8-slot profile was also exercised with 32 Runs:

| repeat | elapsed | throughput | Host B1 : B2 |
| ---: | ---: | ---: | ---: |
| 1 | 55.06 s | 0.581 Runs/s | 15 : 17 |
| 2 | 45.26 s | 0.707 Runs/s | 16 : 16 |
| 3 | 53.35 s | 0.600 Runs/s | 18 : 14 |

Median throughput: **0.600 Runs/s**.

The balanced 16:16 repeat reached **0.707 Runs/s**.

## 5. Scaling interpretation

The architecture did use additional execution compute: moving from four to eight one-CPU Supervisor slots improved the 16-Run median throughput by **25.5%**.

However, scaling efficiency was strongly correlated with Host-level work distribution.

The two Host Agents independently claim from one durable PostgreSQL backlog. Short and medium batches produced distributions such as 9:7, 6:10, 15:17, and 18:14. An imbalanced Host can finish its assigned wave later while capacity on the other Host becomes available.

Therefore the next observed scaling limit is not PostgreSQL throughput. It is **coarse Host-level dispatch imbalance** under independent backlog claiming.

This does not justify a new scheduler implementation in this cycle. It records the next boundary for a future trigger.

## 6. Container-operational evidence

The execution path used:

```text
PostgreSQL
  - authoritative Run / Attempt state
  - durable backlog
  - ownership / lease / accepted completion
        |
        +---------------------+
        |                     |
Host Agent B1            Host Agent B2
  |                         |
4 Supervisors             4 Supervisors
1 CPU / 1.5 GiB each      1 CPU / 1.5 GiB each
        \                   /
             SS Heavy OpenSTA
```

Runtime migration was disabled in workers/Supervisors and applied once before steady-state startup.

Each logical Host used a separate Host identity, epoch, Supervisor pool, execution ownership, and artifact volume.

This supports containerized execution and logical Host separation. It does not support physical failure-domain independence.

## 7. Redis Pub/Sub responsibility

Redis was added only as an ephemeral progress channel:

```text
PostgreSQL state transition
        |
        +--> best-effort progress event
                  |
                  v
              Redis Pub/Sub
                  |
                  v
             subscriber / UI
```

PostgreSQL remains the source of truth.

Implemented events:

- `RUNNING`
- terminal `SUCCEEDED` / `FAILED`

The publisher catches Redis delivery failures and never converts them into execution failures.

No job queue, lock, replay, retention, or ownership responsibility moved to Redis.

## 8. Redis tests

Unit / contract-style regression:

```text
14 tests
OK
```

This set includes:

- event serialization;
- Redis publish failure returns best-effort failure;
- Redis publish failure does not fail a synthetic Run;
- existing PostgreSQL initialization and Host Agent contracts.

Actual Redis + PostgreSQL integration:

```text
test_live_events_are_ephemeral_and_postgres_recovers_current_state ... ok
Ran 1 test
OK
```

The integration verified:

1. a live subscriber received both `RUNNING` and `SUCCEEDED`;
2. a second Run completed successfully with no subscriber connected;
3. after reconnect, current status was recovered from PostgreSQL rather than Redis replay.

This proves the intended responsibility split:

- Redis = transient notification;
- PostgreSQL = durable current state.

## 9. Final targeted regression

With fresh disposable PostgreSQL state and the actual Redis container available on the isolated Docker network:

```text
27 tests
26 passed
1 skipped
```

The skipped integration requires the separately recorded local OpenSTA fixture path that is unavailable inside this test container; it was not counted as a live pass.

The passing set covered PostgreSQL operational claims, Host Agent fencing, supervised completion, Redis progress integration, Redis failure isolation, and PostgreSQL migration/index initialization.

## 10. Verified claims

- additional execution CPU can improve SS Heavy throughput under the current supervised architecture;
- 4→8 execution slots improved the 16-Run median throughput by **25.5%**;
- balanced Host distribution can materially improve scaling efficiency;
- all measured capacity Runs remained `SUCCEEDED/TRUSTED` with uniform provenance;
- Redis Pub/Sub can deliver live progress without becoming part of execution correctness;
- Redis subscriber absence does not affect Run completion;
- reconnecting clients can recover authoritative status from PostgreSQL.

## 11. Unverified claims

- two physical hosts
- independent network/failure domains
- host reboot / network partition throughput
- shared remote artifact storage
- production Redis HA
- production scheduler fairness
- Kubernetes/autoscaling
- Kafka performance
- customer MCMM/sign-off workload
- license-server pressure

## 12. Stop condition

This cycle stops here.

The JD-facing backend slice now has bounded evidence for:

- asynchronous EDA execution;
- relational DB coordination and measured query optimization;
- logical multi-host/container scaling;
- ownership/recovery/fencing;
- report parsing and trusted completion;
- Redis Pub/Sub progress delivery.

Kafka, autoscaling, Kubernetes, and scheduler redesign remain gated behind a new measured requirement.
