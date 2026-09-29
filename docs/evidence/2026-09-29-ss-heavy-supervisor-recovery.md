# SS Heavy Supervisor recovery evidence

## Purpose

Connect the three-corner PVT workload validation to the supervised execution
recovery contract. This record uses the same PicoRV32 x64 Heavy netlist and
the official SKY130 HD SS Liberty as the PVT validation, while keeping the
same-VM container boundary explicit.

## Corner-to-input contract

`OpenStaSubprocessAdapter` now accepts an optional configured corner and
rejects a `JobSpec` whose corner label differs before starting OpenSTA. The SS
Host Agent and Supervisors were configured with:

- `EDA_OPENSTA_CORNER=ss_100C_1v60`
- `EDA_OPENSTA_LIBERTY_PATH=/phase5/sky130_fd_sc_hd__ss_100C_1v60.lib`
- Liberty SHA-256: `9b24f0db3967ac67b4cae1f74bb480fd47922d18d0ed577e3c121739b412c361`
- Heavy netlist SHA-256: `b3f09a42b23a9ff84c0084d4d284a9f8f5830b4c50f4972d68f59a18ea0938ce`

The TT-configured Agent was stopped for this test. The SS Agent then claimed
the Run and recorded the distinct `m1-agent-ss` execution host identity, so
only SS-configured Supervisors could claim its delivery.

## Resource admission observation

The default 384 MiB Supervisor limit produced one OpenSTA child OOM kill before
a timing report could be emitted. Its cgroup recorded `oom=1` and `oom_kill=1`.
This matches the separate PVT measurement's approximately 1.275 GiB peak RSS;
it is a bounded test-environment capacity finding, not a timing/parser error.

With a test-only 2 GiB limit, one SS Heavy Run reached
`SUCCEEDED/TRUSTED` in 26.076497 seconds.

## Live-child Supervisor-loss injection

Two 2 GiB SS Supervisors served the distinct SS Host Agent. Before the loss,
the injector persisted this precondition:

```json
{"supervisor":"phase5-supervisor-ss-2","pid":8,
 "precondition":"docker exec supervisor kill -0 pid succeeded"}
```

It then issued `docker kill` to that Supervisor. The four Run batch converged:

| outcome | count |
| --- | ---: |
| `SUCCEEDED/TRUSTED` | 3 |
| `FAILED/UNKNOWN` | 1 |
| jobs with more than one Attempt | 0 |

The affected Run had one Attempt:
`ABANDONED`, `worker_unavailable`, `recovery_required`. Its delivery became
`UNAVAILABLE` without a termination witness. The other three deliveries were
`COMPLETED` with `PROCESS_EXITED` witnesses.

## Decision and limits

The corner/input contract and fail-closed Supervisor-loss behavior both hold
for the SS Heavy workload. No automatic retry was performed. This is still one
Mac's Docker Linux VM with isolated containers: it does not establish physical
multi-host recovery, remote child observation, shared artifact recovery,
network-partition behavior, or full MCMM sign-off.
