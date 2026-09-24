# Run from this evidence directory. Inputs are explicit environment variables.
read_liberty $::env(EDA_LIB)
read_verilog tiny_mapped.v
link_design tiny
read_sdc $::env(EDA_SDC)
report_units
check_setup -verbose
report_checks -path_delay max -format full_clock_expanded -digits 6 -group_path_count 1
report_worst_slack -max -digits 6
puts "EDA_LAB_REPORT_END"
exit
