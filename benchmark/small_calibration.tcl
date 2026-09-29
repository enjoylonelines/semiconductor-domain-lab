read_liberty /tmp/eda-opensta-20260924/examples/sky130hd_tt.lib
read_verilog docs/evidence/2026-09-24-real-sta/tiny_mapped.v
link_design tiny
read_sdc docs/evidence/2026-09-24-real-sta/normal.sdc
report_checks -path_delay max -digits 6 -group_count 10 -endpoint_count 10
report_worst_slack -max
