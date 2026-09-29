# Heavy PVT-corner workload validation

## Question

Does the calibrated PicoRV32 x64 Heavy workload exercise actual OpenSTA timing
analysis across characterized PVT corners, rather than only serving as a
single-corner process-load fixture?

## Inputs and reproducibility

- PDK distribution: Volare `sky130`, OpenPDK revision
  `f2e289da6753f26157a308c492cf990fdcd4932d`.
- Library: `sky130_fd_sc_hd` from the official Volare artifact.
- Netlist: locally generated PicoRV32 x64 mapped netlist, SHA-256
  `b3f09a42b23a9ff84c0084d4d284a9f8f5830b4c50f4972d68f59a18ea0938ce`.
- Constraint: the same 10 ns setup-max SDC embedded in
  `benchmark/picorv32x64_calibration.tcl` for every corner.
- Tool: OpenSTA `396536743ff33852cd8af176988f077219bc8b8d`, macOS arm64.

Raw stdout, stderr, and per-corner summaries are versioned under
`benchmark/raw/pvt-f2e289/`. The PDK itself is intentionally not copied into
the repository; the pinned Volare revision and file hashes are the provenance
record.

## Parser and execution acceptance

Each corner linked the same 927 KiB mapped netlist, produced
`EDA_LAB_REPORT_END`, and returned exit code zero in five of five runs.

| PVT corner | Liberty SHA-256 | valid runs | median real time | p95 real time | max RSS |
| --- | --- | ---: | ---: | ---: | ---: |
| TT, 25 C, 1.80 V | `8e78e144…31487135` | 5/5 | 7.34 s | 7.38 s | 1,275,805,696 B |
| FF, -40 C, 1.95 V | `fb61d91c…30720139` | 5/5 | 7.38 s | 7.40 s | 1,275,117,568 B |
| SS, 100 C, 1.60 V | `9b24f0db…b412c361` | 5/5 | 7.45 s | 7.56 s | 1,274,626,048 B |

The cost envelope is similar for this graph size and host. This does not make
the corners equivalent for timing: the first report in each raw set has the
same startpoint and endpoint, but distinct worst setup slack values:

| PVT corner | worst setup slack |
| --- | ---: |
| FF | -0.772329 ns |
| TT | -5.596185 ns |
| SS | -16.873129 ns |

The direction and magnitude distinguish library characterization effects from
a pure parser or process-load loop. All three reports violate the deliberately
tight 10 ns constraint; this is a timing stress condition, not a functional
mode assertion.

## Decision and limits

The Heavy workload is accepted as a bounded three-corner PVT workload for
future execution-cost and recovery experiments. It is not full MCMM sign-off:
there is one functional netlist/constraint mode, no scan mode, no SPEF or
post-layout parasitics, no operating-condition matrix beyond these three
Liberty corners, and no physical multi-host capacity claim. The prior
single-corner performance evidence remains valid only for its recorded input;
new comparisons must cite the PVT raw set above.

The SS corner has also been exercised through the supervised live-child loss
path; see [SS Heavy Supervisor recovery evidence](2026-09-29-ss-heavy-supervisor-recovery.md).
