# SPDX-License-Identifier: Apache-2.0
# Independent OOC synthesis only: no board design, bitstream or hardware access.
if {[version -short] ne "2020.1"} {error "This evidence profile requires Vivado 2020.1"}
if {$argc != 1} {error "usage: synth_ooc.tcl NEW_OUTPUT_DIRECTORY"}
set out [file normalize [lindex $argv 0]]
if {[file exists $out]} {error "Output exists; preserve earlier evidence"}
file mkdir $out
set root [file normalize [file join [file dirname [info script]] ..]]
create_project -in_memory -part xczu19eg-ffvc1760-2-i
set_param general.maxThreads 1
read_verilog -sv [file join $root rtl vg_sort_guard_core.sv]
read_verilog -sv [file join $root rtl vg_sort_guard_axi.sv]
synth_design -top vg_sort_guard_axi -part xczu19eg-ffvc1760-2-i -mode out_of_context
create_clock -name guard_clk -period 10.000 [get_ports clk]
report_utilization -file [file join $out utilization.rpt]
report_timing_summary -file [file join $out timing_synth_only.rpt]
report_drc -file [file join $out drc_synth_only.rpt]
write_checkpoint [file join $out sort_guard_ooc.dcp]
puts "SORT_GUARD_SYNTH_PASS: OOC only; no placement, routing, bitstream or board validation"
exit
