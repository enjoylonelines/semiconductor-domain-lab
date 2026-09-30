# SS Heavy scaling and queued-lease closure

## Finding(발견) and root cause(근본 원인)

The first true one-Supervisor(감독자) run exposed five `UNAVAILABLE` deliveries.
The Host Agent(호스트 에이전트) created an Attempt(실행 시도) lease before
enqueueing its delivery, but only a claimed Supervisor refreshed that lease.
Queued work could therefore outlive its 30-second lease and be reconciled as a
lost worker before any child started.

`HostAgent.heartbeat()` now refreshes only `QUEUED` delivery leases belonging to
its live fenced session. It stops at `CLAIMED`, where the existing Supervisor
heartbeat owns liveness. This preserves recovery for a lost Supervisor while
preventing queue wait from being misclassified as worker loss.

The pre-fix one- and two-Supervisor outputs are retained as `rejected-*` raw
records. They are excluded because all four Supervisors were accidentally live
in the first pair, and the next one-Supervisor run exposed the lease defect.

## Measured contract(측정 계약)

Each accepted point used the pinned SS Liberty and Heavy netlist, eight fixed
Runs per batch, three batches, one CPU and 1.5 GiB per Supervisor, and the
same Docker Linux VM. Every accepted Run recorded the Heavy netlist SHA-256
`b3f09a42b23a9ff84c0084d4d284a9f8f5830b4c50f4972d68f59a18ea0938ce`.

| Supervisors | accepted completion | median makespan | observer p95 makespan | median queue wait | observer p95 queue wait |
| ---: | --- | ---: | ---: | ---: | ---: |
| 1 | 24/24 `SUCCEEDED/TRUSTED` | 75.513 s | 77.484 s | 37.352 s | 65.407 s |
| 2 | 24/24 `SUCCEEDED/TRUSTED` | 38.760 s | 39.004 s | 19.176 s | 28.839 s |
| 4 | 24/24 `SUCCEEDED/TRUSTED` | 20.789 s | 21.119 s | 9.831 s | 10.248 s |
| 8 | 24/24 `SUCCEEDED/TRUSTED` | 12.743 s | 13.182 s | 0.283 s | 0.425 s |

The 1→2, 2→4, and 4→8 median makespan reductions are 48.7%, 46.4%, and 38.7%.
All values remain a bounded same-VM result, not a physical multi-host claim.

## Decision(결정) and limit(한계)

Keep eight SS Heavy slots as the tested upper profile for this VM: it removes
the observed queue backlog and completed every accepted run without OOM in the
earlier eight-way admission test. CPU is saturated at each one-CPU Supervisor;
PostgreSQL lock wait was zero in the eight-way observation. Neither fact proves
that eight is a production optimum or opens a Kafka trigger.

This closes the fixed-batch scaling question. Sustained arrivals, mixed corners,
timeout/cancellation under load, physical multi-host capacity, and license-seat
pressure remain separate experiments.
