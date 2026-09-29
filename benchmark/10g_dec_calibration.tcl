read_liberty /tmp/sky130hd_tt.lib
read_verilog /tmp/xgmii_baser_dec_64_sky130hd.v
link_design xgmii_baser_dec_64
create_clock -name clk -period 6.4 [get_ports clk]
set_input_delay 0.5 -clock clk [get_ports {rst encoded_rx_data* encoded_rx_hdr*}]
set_output_delay 0.5 -clock clk [all_outputs]
set_input_transition 0.1 [all_inputs]
set_load 0.05 [all_outputs]
report_checks -path_delay max -digits 6 -group_count 5 -endpoint_count 5
report_worst_slack -max
