# Future explicit build only. Never invoked by source delivery or CI here.
if {$argc != 2} {error "Expected PROJECT_XPR and NEW_XSA_PATH"}
set xsa [file normalize [lindex $argv 1]]
if {[file exists $xsa]} {error "XSA output already exists"}
open_project [lindex $argv 0]
if {[get_property PART [current_project]] ne "xczu19eg-ffvc1760-2-i"} {error "Wrong part"}
if {[get_property TOP [current_fileset]] ne "system_pspl_wrapper"} {error "Wrong profile"}
launch_runs synth_1 -jobs 2
wait_on_run synth_1
if {[get_property STATUS [get_runs synth_1]] ne "synth_design Complete!"} {error "Synthesis did not complete"}
launch_runs impl_1 -to_step write_bitstream -jobs 2
wait_on_run impl_1
if {[get_property STATUS [get_runs impl_1]] ne "write_bitstream Complete!"} {error "Implementation did not complete"}
open_run impl_1
write_hw_platform -fixed -include_bit $xsa
