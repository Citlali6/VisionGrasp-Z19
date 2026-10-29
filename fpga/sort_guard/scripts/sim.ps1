param(
    [Parameter(Mandatory=$true)][string]$VivadoBin,
    [Parameter(Mandatory=$true)][string]$OutputDirectory
)
$ErrorActionPreference = 'Stop'
$sourceRoot = (Split-Path -Parent $PSScriptRoot).Replace('\', '/')
if (Test-Path -LiteralPath $OutputDirectory) { throw 'Output exists; choose a new evidence directory.' }
New-Item -ItemType Directory -Path $OutputDirectory | Out-Null
Push-Location -LiteralPath $OutputDirectory
try {
    & "$VivadoBin/xvlog.bat" --sv "$sourceRoot/rtl/vg_sort_guard_core.sv" "$sourceRoot/rtl/vg_sort_guard_axi.sv" "$sourceRoot/sim/tb_sort_guard.sv"
    if ($LASTEXITCODE -ne 0) { throw "xvlog failed: $LASTEXITCODE" }
    & "$VivadoBin/xelab.bat" tb_sort_guard --timescale 1ns/1ps -s sort_guard
    if ($LASTEXITCODE -ne 0) { throw "xelab failed: $LASTEXITCODE" }
    & "$VivadoBin/xsim.bat" sort_guard -tclbatch "$sourceRoot/sim/run.tcl" -log simulation.log
    if ($LASTEXITCODE -ne 0) { throw "xsim failed: $LASTEXITCODE" }
    $log = Get-Content -LiteralPath simulation.log -Raw
    if ($log -notmatch 'SORT_GUARD_PASS' -or $log -match '(?m)^(Fatal:|ERROR:)') { throw 'SORT_GUARD simulation did not pass.' }
} finally { Pop-Location }
