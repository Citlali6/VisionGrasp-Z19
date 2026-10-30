# SPDX-License-Identifier: Apache-2.0
# Authoring entry: intentionally not run in the 2026-10-30 source delivery.
# Usage (future): vivado -mode batch -source create_project.tcl -tclargs NEW_OUTPUT
if {$argc != 1} {error "Expected an unused output directory"}
if {[version -short] ne "2020.1"} {error "This profile pins Vivado 2020.1; do not upgrade IP implicitly"}
set out [file normalize [lindex $argv 0]]
if {[file exists $out]} {error "Refusing to overwrite existing output"}
set profile_root [file dirname [file normalize [info script]]]
set repo_root [file normalize [file join $profile_root ../..]]
source [file join $profile_root profile.tcl]
create_project z19_pspl_four_functions [file join $out project] -part $device_part
set source_list [open [file join $profile_root sources.f] r]
set source_text [read $source_list]
close $source_list
set rtl_files [list]
foreach relative [split $source_text "\n"] {
    set relative [string trim $relative]
    if {$relative eq "" || [string match "#*" $relative]} {continue}
    lappend rtl_files [file normalize [file join $repo_root $relative]]
}
if {[llength $rtl_files] != 18} {error "Incomplete PS/PL source set"}
foreach source_file $rtl_files {
    if {![file isfile $source_file]} {error "Missing source: $source_file"}
}
add_files -norecurse $rtl_files
set_property include_dirs [list [file join $profile_root rtl]] [current_fileset]
update_compile_order -fileset sources_1
source [file join $profile_root build_bd.tcl]
save_bd_design
generate_target all [get_files */system_pspl.bd]
add_files -norecurse [make_wrapper -files [get_files */system_pspl.bd] -top]
set_property top system_pspl_wrapper [current_fileset]
update_compile_order -fileset sources_1
# No synthesis/implementation is launched by project creation.
