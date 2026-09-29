read_liberty /tmp/eda-opensta-20260924/examples/sky130hd_tt.lib
read_verilog /tmp/picorv32_sky130hd.v
link_design picorv32
create_clock -name clk -period 10 [get_ports clk]
set_input_delay 1 -clock clk [get_ports {resetn mem_ready mem_rdata* pcpi_wr pcpi_rd* pcpi_wait pcpi_ready irq*}]
set_output_delay 1 -clock clk [get_ports {trap mem_valid mem_instr mem_addr* mem_wdata* mem_wstrb* mem_la_read mem_la_write mem_la_addr* mem_la_wdata* mem_la_wstrb* pcpi_valid pcpi_insn* pcpi_rs1* pcpi_rs2* eoi* trace_valid trace_data*}]
set_input_transition 0.1 [all_inputs]
set_load 0.05 [all_outputs]
report_checks -path_delay max -fields {slew cap input_pin} -digits 6 -group_count 10 -endpoint_count 10
report_worst_slack -max
