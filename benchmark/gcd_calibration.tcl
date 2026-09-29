read_liberty /tmp/eda-opensta-20260924/examples/sky130hd_tt.lib
read_verilog /tmp/eda-opensta-20260924/examples/gcd_sky130hd.v
link_design gcd
read_sdc /tmp/eda-opensta-20260924/examples/gcd_sky130hd.sdc
report_checks -path_delay max -digits 6 -group_count 10 -endpoint_count 10
report_worst_slack -max
