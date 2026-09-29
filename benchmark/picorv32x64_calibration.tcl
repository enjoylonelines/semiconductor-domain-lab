read_liberty /tmp/sky130hd_tt.lib
read_verilog /tmp/picorv32x64_sky130hd.v
link_design picorv32_bench_top
create_clock -name clk -period 10 [get_ports clk]
set_input_delay 1 -clock clk [get_ports {resetn mem_ready mem_rdata* pcpi_wr pcpi_rd* pcpi_wait pcpi_ready irq*}]
set_output_delay 1 -clock clk [get_ports {trap*}]
set_input_transition 0.1 [all_inputs]
set_load 0.05 [all_outputs]
report_checks -path_delay max -digits 6 -group_count 10 -endpoint_count 10
report_worst_slack -max
