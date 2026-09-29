read_liberty $::env(EDA_LIB)
read_verilog $::env(EDA_NETLIST)
link_design picorv32_bench_top
create_clock -name clk -period 10 [get_ports clk]
set_input_delay 1 -clock clk [get_ports {resetn mem_ready mem_rdata* pcpi_wr pcpi_rd* pcpi_wait pcpi_ready irq*}]
set_output_delay 1 -clock clk [get_ports {trap*}]
set_input_transition 0.1 [all_inputs]
set_load 0.05 [all_outputs]
report_units
report_checks -path_delay max -digits 6 -group_path_count 1 -endpoint_path_count 1
report_worst_slack -max -digits 6
puts "EDA_LAB_REPORT_END"
exit
