# SPDX-License-Identifier: Apache-2.0
# Sourced by create_project.tcl; all streaming, PIO, guard and reset logic uses
# one PS-derived PL clock. USB/audio sample cadence is data, not another clock.
create_bd_design system_pspl
create_bd_cell -type ip -vlnv xilinx.com:ip:zynq_ultra_ps_e:3.3 ps0
source [file join $repo_root fpga scripts alinx ps_config.tcl]
set_ps_config ps0
set_property -dict [list CONFIG.PSU__USE__M_AXI_GP0 {1} \
    CONFIG.PSU__USE__M_AXI_GP1 {0} CONFIG.PSU__USE__M_AXI_GP2 {0} \
    CONFIG.PSU__MAXIGP0__DATA_WIDTH {128} CONFIG.PSU__FPGA_PL0_ENABLE {1} \
    CONFIG.PSU__FPGA_PL1_ENABLE {1} CONFIG.PSU__CRL_APB__PL1_REF_CTRL__FREQMHZ $logic_clock_mhz \
    CONFIG.PSU__CRL_APB__PL1_REF_CTRL__SRCSEL {RPLL}] [get_bd_cells ps0]
create_bd_cell -type module -reference vg_video_axi_top video0
create_bd_cell -type module -reference vg_audio_axi_top audio0
create_bd_cell -type module -reference vg_guard_axi_top guard0
create_bd_cell -type ip -vlnv xilinx.com:ip:axi_interconnect:2.1 axi_ic
set_property -dict [list CONFIG.NUM_MI {3} CONFIG.NUM_SI {1}] [get_bd_cells axi_ic]
create_bd_cell -type ip -vlnv xilinx.com:ip:proc_sys_reset:5.0 reset0
set_property -dict [list CONFIG.C_EXT_RESET_HIGH {0} CONFIG.C_AUX_RESET_HIGH {0}] [get_bd_cells reset0]
create_bd_cell -type ip -vlnv xilinx.com:ip:xlconstant:1.1 zero
set_property CONFIG.CONST_VAL {0} [get_bd_cells zero]
create_bd_cell -type ip -vlnv xilinx.com:ip:xlconstant:1.1 one
set_property CONFIG.CONST_VAL {1} [get_bd_cells one]
connect_bd_intf_net [get_bd_intf_pins ps0/M_AXI_HPM0_FPD] [get_bd_intf_pins axi_ic/S00_AXI]
foreach {index cell} {0 video0 1 audio0 2 guard0} {
    set mi [format M%02d_AXI $index]
    connect_bd_intf_net [get_bd_intf_pins axi_ic/$mi] [get_bd_intf_pins $cell/s_axi]
    connect_bd_net [get_bd_pins ps0/pl_clk1] [get_bd_pins axi_ic/[format M%02d_ACLK $index]] [get_bd_pins $cell/clk]
    connect_bd_net [get_bd_pins reset0/peripheral_aresetn] [get_bd_pins axi_ic/[format M%02d_ARESETN $index]] [get_bd_pins $cell/rst_n]
}
connect_bd_net [get_bd_pins ps0/pl_clk1] [get_bd_pins ps0/maxihpm0_fpd_aclk] \
    [get_bd_pins axi_ic/ACLK] [get_bd_pins axi_ic/S00_ACLK] [get_bd_pins reset0/slowest_sync_clk]
connect_bd_net [get_bd_pins ps0/pl_resetn0] [get_bd_pins reset0/ext_reset_in]
connect_bd_net [get_bd_pins zero/dout] [get_bd_pins reset0/mb_debug_sys_rst]
connect_bd_net [get_bd_pins one/dout] [get_bd_pins reset0/dcm_locked] [get_bd_pins reset0/aux_reset_in]
connect_bd_net [get_bd_pins reset0/interconnect_aresetn] [get_bd_pins axi_ic/ARESETN]
connect_bd_net [get_bd_pins reset0/peripheral_aresetn] [get_bd_pins axi_ic/S00_ARESETN]
foreach {cell address span} [list video0 $video_base $video_range audio0 $audio_base $audio_range guard0 $guard_base $guard_range] {
    assign_bd_address -target_address_space /ps0/Data [get_bd_addr_segs $cell/s_axi/reg0] -offset $address -range $span
}
# Guard permit remains PS-readable task data; no actuator pin is exported.
validate_bd_design
