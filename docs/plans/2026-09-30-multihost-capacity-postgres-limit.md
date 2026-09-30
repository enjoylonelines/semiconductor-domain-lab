# Multi-host correctness → capacity → PostgreSQL limit cycle

Date: 2026-09-30
Base revision: dd432bc
Status: closed after reproducing a PostgreSQL coordination ceiling at 32 synthetic claimers, evaluating one partial-index correction, and keeping Kafka gated for the current real SS Heavy profile. See `../evidence/2026-09-30-multihost-and-postgres-coordination-limit.md` and `../decisions/2026-09-30-postgres-coordination-ceiling.md`.

## Goal

Continue from the closed SS Heavy backlog cycle until the next PostgreSQL coordination limit is actually observed or the bounded environment reaches its stop condition.

Sequence:
1. revalidate logical two-host ownership/recovery correctness on the current revision;
2. measure what can and cannot be claimed about OpenSTA capacity scaling in the available single Docker VM;
3. isolate PostgreSQL coordination from OpenSTA CPU and increase coordination concurrency/backlog until a repeatable DB-side limit appears;
4. if a DB-side limit appears, allow one PostgreSQL repair and rerun the same condition;
5. open Kafka only if the structural delivery responsibility remains the bottleneck.

## Multi-host correctness invariants

- Host epoch/session fencing rejects stale completion.
- A foreign Host never treats another Host's PID as local liveness evidence.
- A confirmed-live execution is never overlapped by a new Attempt.
- PROCESS_EXITED/RUNTIME_TERMINATED witness is not accepted success by itself.
- Worker/Host Agent loss while Supervisor remains live does not cause false lease-expiry recovery.
- Old Host/session/lease tokens cannot accepted-complete after ownership changes.

This cycle may use logical hosts in distinct containers/PID namespaces sharing PostgreSQL. It must not call that physical multi-host proof.

## Capacity boundary

The available Docker VM has eight CPUs. Starting sixteen CPU-bound SS Heavy Supervisors in that same VM cannot prove two-host horizontal capacity scaling because physical CPU capacity did not increase.

Therefore:
- retain 1 Host x 8 SS Heavy as the validated execution-capacity baseline;
- use two logical Host identities only for correctness/distribution tests;
- do not claim 2x OpenSTA throughput without a second physical compute budget;
- find the PostgreSQL coordination limit separately with a controlled short/synthetic execution adapter so DB delivery/claim cost can become visible without OpenSTA CPU hiding it.

## PostgreSQL limit experiment

Keep PostgreSQL config fixed first. Increase coordination concurrency and queued Runs in bounded stages.

Candidate stages:
- workers 8 / 16 / 32 / 64
- queued Runs 128 / 512 / 2048, only as needed

Measure:
- actual claim_next_run call latency p50/p95/p99
- submit/create_run latency p50/p95/p99
- throughput
- lock waits
- DB connections
- deadlock / serialization / transaction errors
- idle worker/slot time while queued work exists
- correctness: one accepted completion per Run, one effective claim, terminal convergence

Do not use execution-request created→claimed residence as SQL claim latency.

## DB bottleneck trigger

A DB-side limit is supported only when repeated evidence shows one or more:
- claim_next_run call latency rises materially with concurrency/backlog;
- worker slots are idle while queued work exists because claim/delivery cannot feed them;
- lock waits or connection pressure recur;
- deadlock/serialization/transaction errors recur;
- throughput plateaus or falls while the controlled execution adapter is not the limiting resource.

## One PostgreSQL repair budget

After reproducing the limit:
1. inspect the actual SQL with EXPLAIN (ANALYZE, BUFFERS) where applicable;
2. identify one reasonable index/query/config correction;
3. apply only that bounded correction;
4. rerun the same failing stage;
5. stop and compare before considering Kafka.

## Stop conditions

- If DB bottleneck is reproduced and one PostgreSQL correction is evaluated, close the cycle.
- If the bounded maximum still shows no DB coordination limit, record the tested ceiling and stop rather than inventing a larger production claim.
- Kafka remains gated behind a structural delivery limitation after the PostgreSQL repair attempt.
