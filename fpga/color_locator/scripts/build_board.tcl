# Independent PS/PL diagnostic image; no board programming or boot-file writes.
if {$argc!=1} {error "Expected new output directory"}
set out [file normalize [lindex $argv 0]]
if {[file exists $out]} {error "Output directory exists"}
file mkdir $out
set root [file normalize [file join [file dirname [info script]] ..]]
create_project pl_color [file join $out project] -part xczu19eg-ffvc1760-2-i
add_files -norecurse [list [file join $root vendor laperex cv_types.sv] [file join $root vendor laperex cv_rgb_to_hsv.sv] [file join $root rtl vg_color_axis.sv] [file join $root rtl vg_color_axi.sv]]
add_files -norecurse [file join $root rtl vg_color_axi_top.v]
update_compile_order -fileset sources_1
create_bd_design color_bd
create_bd_cell -type ip -vlnv xilinx.com:ip:zynq_ultra_ps_e:3.3 ps0
source [file join $root .. scripts alinx ps_config.tcl]
set_ps_config ps0
set_property -dict [list CONFIG.PSU__USE__M_AXI_GP0 {1} CONFIG.PSU__USE__M_AXI_GP1 {0} CONFIG.PSU__USE__M_AXI_GP2 {0} CONFIG.PSU__MAXIGP0__DATA_WIDTH {128} CONFIG.PSU__FPGA_PL0_ENABLE {1} CONFIG.PSU__FPGA_PL1_ENABLE {1} CONFIG.PSU__CRL_APB__PL0_REF_CTRL__FREQMHZ {200.000} CONFIG.PSU__CRL_APB__PL1_REF_CTRL__FREQMHZ {100.000} CONFIG.PSU__CRL_APB__PL0_REF_CTRL__SRCSEL {RPLL} CONFIG.PSU__CRL_APB__PL1_REF_CTRL__SRCSEL {RPLL}] [get_bd_cells ps0]
create_bd_cell -type module -reference vg_color_axi_top color0
create_bd_cell -type ip -vlnv xilinx.com:ip:axi_interconnect:2.1 axi_ic
set_property -dict [list CONFIG.NUM_MI {1} CONFIG.NUM_SI {1}] [get_bd_cells axi_ic]
create_bd_cell -type ip -vlnv xilinx.com:ip:proc_sys_reset:5.0 rst_ps
set_property -dict [list CONFIG.C_EXT_RESET_HIGH {0} CONFIG.C_AUX_RESET_HIGH {0}] [get_bd_cells rst_ps]
create_bd_cell -type ip -vlnv xilinx.com:ip:xlconstant:1.1 zero
set_property CONFIG.CONST_VAL {0} [get_bd_cells zero]
create_bd_cell -type ip -vlnv xilinx.com:ip:xlconstant:1.1 one
set_property CONFIG.CONST_VAL {1} [get_bd_cells one]
connect_bd_intf_net [get_bd_intf_pins ps0/M_AXI_HPM0_FPD] [get_bd_intf_pins axi_ic/S00_AXI]
connect_bd_intf_net [get_bd_intf_pins axi_ic/M00_AXI] [get_bd_intf_pins color0/s_axi]
connect_bd_net [get_bd_pins ps0/pl_clk1] [get_bd_pins ps0/maxihpm0_fpd_aclk] [get_bd_pins axi_ic/ACLK] [get_bd_pins axi_ic/S00_ACLK] [get_bd_pins axi_ic/M00_ACLK] [get_bd_pins color0/clk] [get_bd_pins rst_ps/slowest_sync_clk]
connect_bd_net [get_bd_pins ps0/pl_resetn0] [get_bd_pins rst_ps/ext_reset_in]
connect_bd_net [get_bd_pins zero/dout] [get_bd_pins rst_ps/mb_debug_sys_rst]
connect_bd_net [get_bd_pins one/dout] [get_bd_pins rst_ps/dcm_locked] [get_bd_pins rst_ps/aux_reset_in]
connect_bd_net [get_bd_pins rst_ps/interconnect_aresetn] [get_bd_pins axi_ic/ARESETN]
connect_bd_net [get_bd_pins rst_ps/peripheral_aresetn] [get_bd_pins axi_ic/S00_ARESETN] [get_bd_pins axi_ic/M00_ARESETN] [get_bd_pins color0/rst_n]
assign_bd_address -target_address_space /ps0/Data [get_bd_addr_segs color0/s_axi/reg0] -offset 0xA0000000 -range 4K
validate_bd_design
save_bd_design
set bd [get_files */color_bd.bd]
generate_target all $bd
set wrapper [make_wrapper -files $bd -top]
add_files -norecurse $wrapper
set_property top color_bd_wrapper [current_fileset]
update_compile_order -fileset sources_1
launch_runs synth_1 -jobs 2
wait_on_run synth_1
if {[get_property STATUS [get_runs synth_1]] ne "synth_design Complete!"} {error "Synthesis failed"}
launch_runs impl_1 -to_step write_bitstream -jobs 2
wait_on_run impl_1
if {[get_property STATUS [get_runs impl_1]] ne "write_bitstream Complete!"} {error "Implementation failed"}
open_run impl_1
report_drc -file [file join $out drc.rpt]
report_timing_summary -file [file join $out timing.rpt]
report_utilization -file [file join $out utilization.rpt]
if {[get_property SLACK [get_timing_paths -delay_type max -max_paths 1]]<0} {error "Timing failed"}
write_hw_platform -fixed -include_bit [file join $out color.xsa]
file copy [file join [get_property DIRECTORY [get_runs impl_1]] color_bd_wrapper.bit] [file join $out color.bit]
puts "COLOR_BOARD_BUILD_PASS"
exit
