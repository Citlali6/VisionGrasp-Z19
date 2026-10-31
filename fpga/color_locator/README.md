# PL color segmentation: Z19 USB-camera diagnostic

**Status (2026-10-22): RTL tests, full implementation, real Z19 PL self-test and
1280×720 USB-camera processing passed.** The PC displays the original and the
PL-highlighted image at `http://127.0.0.1:8774/` while the bench processes and
SSH tunnel remain running. This is color segmentation and a global bounding
rectangle. The later browser grid mapping and coordinate speech are described below;
same-color object separation and arm control remain unimplemented.

**Optional voice selection (2026-10-22):** real user speech selected red and a later
board status showed a voice-originated green request with matching camera/PL frame
IDs and PL coordinates. ASR runs on Z19 ARM using the existing Chinese small model;
HSV, pixel count and bounding rectangle remain in PL. See [voice setup and evidence](VOICE.md).
These additions are separate from the frozen r3 firmware/executable bundle below.

The [physical grid coordinates and balanced preview](GRID.md) preserve
the 720p source field of view while sending a half-size 640x360 image through PL.
Measured board publication rose from 1.92 fps to 7.26 fps; actual browser display was
about 7.2 fps. This is a lower PL processing resolution, not full-resolution 720p acceleration.
Voice-selected targets can be announced in board coordinates using the USB speaker,
with explicit Chinese decimal pronunciation. See [GRID.md](GRID.md) and [VOICE.md](VOICE.md).

Validated firmware, reports and file hashes are under `deliverables/pl_color_z19/`.

## Data flow and interfaces

```text
USB UVC MJPEG -> Z19 PS JPEG decode -> native32 AXI-Lite PIO -> vg_color_axis
       RGB -> HSV -> selected-color mask -> PL highlight + global statistics
       -> native32 PIO -> Z19 PS JPEG encode -> SSH tunnel -> PC browser display
```

The source must deliver one unpacked 32-bit word per pixel (`0x00RRGGBB`). MJPEG,
YUYV, RGB565 and packed 24-bit byte streams cannot be connected directly.
PL color masking, pixel counts and the global bounding box are computed on the board.
The browser maps that box center onto the calibrated physical grid; it does not
replace the PL color algorithm.

All ports are in `aclk`. Assert `aresetn` low for at least one clock, and deassert
synchronously. Any other clock domain requires a reviewed AXI-stream clock FIFO;
this component itself does not implement CDC or a USB protocol controller.

| Port | Meaning |
| --- | --- |
| `s_axis_tdata[31:0]` | one RGB888 pixel, high byte reserved |
| `s_axis_tvalid/tready` | consume only when both high; source holds data/flags while stalled |
| `s_axis_tuser` | first pixel of frame (SOF) |
| `s_axis_tlast` | last pixel of each line (EOL), **not DMA frame EOF** |
| `cfg_color[1:0]` | 0 off; 1 red; 2 green; 3 blue; sampled on an accepted SOF |
| `cfg_min_s/cfg_min_v[7:0]` | HSV minimum saturation/value, sampled at the same SOF |
| `m_axis_tdata[31]` | selected-color mask |
| `m_axis_tdata[30:24]` | zero |
| `m_axis_tdata[23:0]` | unchanged original RGB pixel |
| `m_axis_tuser/tlast` | aligned input SOF/EOL flags |
| `m_axis_tvalid/tready` | sink backpressure supported, output held until consumed |

Hue uses the OpenCV-style 0..179 scale. Red ranges0..10 and170..179, green35..85,
blue95..135 are inclusive. `cfg_min_s=100`, `cfg_min_v=80` are example diagnostic
settings; real camera/light conditions must be calibrated. The core is fixed-point
and can differ from float/OpenCV results near thresholds. Pixels before the first
SOF pass through with mask0. Color off takes effect on the next accepted SOF;
this is not an emergency-stop interface. Config does not change a frame midway.

FIFO_DEPTH defaults16 and must be a power of two >=8. One credit is reserved per
accepted input beat, including pixels still inside the upstream six-register
pipeline; it is returned only when the downstream consumes a result. FIFOs alone
without this reservation would not solve upstream's free-running core limitation.

The input and output transfer can reach one pixel per clock after pipeline fill
when unstalled. There is no frame buffer. Resolution is not hardcoded; framing
must be supplied correctly by the adapter. Neither 720p30 USB capture nor its
end-to-end 30fps video bandwidth has been verified with this component. The
initial board diagnostic uses PIO and measured about 0.83–0.86 seconds per 720p
frame for its MMIO/PL round trip; this is not the HSV pipeline latency. A later
transport optimization measured about0.47s at720p and0.157s at640×480 with capture
active. The browser now offers both resolutions; see the measurements below.

## Reproducible simulation

Existing Vivado2020.1 tools and any Python3 with the standard library are sufficient.
Choose new output directories; scripts refuse to overwrite evidence.

```powershell
& fpga/color_locator/scripts/sim.ps1 `
  -VivadoBin "$env:VIVADO_2020_1_BIN" `
  -PythonExe 'python' `
  -OutputDirectory '../color-sim-new'
```

Success requires `HSV_PASS`, `COLOR_AXIS_PASS` and `COLOR_AXI_PASS`; the runner checks markers and
fatal errors rather than trusting xsim's process exit code alone.

- Numeric reference: 1024 RGB samples; circular H error <=1, S error <=2, V exact;
  valid bubbles and TLAST alignment checked. Offline float reference only.
- Streaming: 2064 beats covering red/green/blue/off, black/white/gray/yellow,
  dim red, SOF/EOL, bubbles, prolonged stalls, configuration changes within frames,
  before-first-SOF behavior, and reset while pixels remain in flight.
- Backpressure run: 3910 source-stall cycles, 4108 output-hold checks, no pixel
  mismatch or credit overflow in that test. Not an exhaustive protocol proof.

## OOC synthesis

Set `VIVADO_2020_1_BIN` to the installed Vivado 2020.1 `bin` directory.
Run Vivado from a separate scratch working directory to keep its logs out of the
source tree; from the repository root, resolve the script before changing directory:

```powershell
$script = (Resolve-Path 'fpga/color_locator/scripts/synth_ooc.tcl').Path
$scratch = New-Item -ItemType Directory '../color-synth-scratch-new'
Push-Location $scratch.FullName
try {
  & "$env:VIVADO_2020_1_BIN/vivado.bat" -mode batch -source $script `
    -tclargs "$($scratch.FullName)/reports-new"
} finally { Pop-Location }
```

Actual first OOC run: XCZU19EG-FFVC1760-2-I, 379 LUTs, 374 FFs, 0 BRAM tiles,
**4 DSPs**. These are the final utilization-report totals, not intermediate
primitive counts. Synthesized-netlist timing under a 10ns clock reported WNS
6.014ns; this is **not routed timing closure or demonstrated Fmax**. OOC lacks
top-level clock-source/skew and I/O timing context (`HD.CLK_SRC` warning). No
bitstream is generated by this script.

## Reuse and limits

`vendor/laperex` contains two unmodified MIT-licensed upstream files and its
license/commit/hash manifest. The local wrapper, tests and scripts are new code.
The upstream PYNQ-Z2 BD, unsafe ready passthrough and large auto-assigned AXI
address segment are not reused. The new standalone BD explicitly assigns the
color endpoint `0xA0000000`, range4KiB. This address is valid only with this
reviewed color image; do not probe it with the factory, MIPI or MJC1 image.

The reusable stream accelerator produces per-pixel masks. The diagnostic AXI
bridge adds PL pixel count and one global bounding rectangle; separate same-color
objects are merged. Browser grid coordinates use the [separate grid mapping](GRID.md);
component separation and calibrated arm coordinates remain unimplemented.
Only the reviewed color firmware contains this IP; the MIPI camera profile is separate.

## Board profile, safety checks and reproduction

See [board instructions and register map](BOARD.md). The source files are:

- `rtl/vg_color_axi.sv`: bounded AXI-Lite endpoint and PL highlight/statistics.
- `rtl/vg_color_axi_top.v`: Vivado2020.1-compatible Verilog BD entry wrapper.
- `scripts/build_board.tcl`: independent PS/PL image, FPD bus and reviewed resets.
- `host/color_camera.c`: native AArch64 USB/JPEG/MMIO transport; no CPU HSV.
- `host/load_color.sh`: hash/profile/clock/driver guard before loading via PCAP.
- `host/preview.py`: board-local HTTP display/control server, standard library only.

Full implementation used 1885 LUTs, 1936 FFs, 0 BRAM and 6 DSPs, including AXI
interconnect/bridge. Routed WNS4.580ns, WHS0.017ns, no timing failures. DRC had
0 errors and25 warnings (DSP pipelining suggestions and unused vendor-IP nets),
not a warning-free result. The board's measured PL1 clock was100.351990MHz.
No external PL camera/actuator pins are used by this diagnostic image.

## Lower-latency preview (same PL image)

After the user reported lag, the board-side transport was optimized without
reprogramming PL or moving HSV to a CPU. Native32 access and full memory barriers
remain; batches of16 fit the exact reviewed FIFO and avoid redundant per-pixel
status queries. A dedicated USB thread keeps only the latest compressed frame,
independent of the processing thread. JPEG decode/encode remain PS transport.
The browser preloads a same-frame source/result pair before displaying it,
polls every80ms without accumulating requests, and uses HTTP keep-alive.

| Mode | Actual resolution | Board publication rate | Capture timestamp to publication |
|---|---|---|---|
| Low latency (default) |640×480|5.76fps average,24 distinct sampled frames|221.43ms average,203.80–238.17ms|
| HD |1280×720|1.93fps average,10 distinct sampled frames|561.76ms average,547.73–573.44ms|

These are board measurements, not camera-advertised FPS or measured screen/glass
latency. Browser/network time is additional. Neither mode reaches30fps; full-HD
transport performance still calls for a reviewed DMA path. The same native PL
benchmark checked4,915,200 returned pixels across both sizes and all four color
modes with no mismatch; camera and PL frame IDs matched in the sampled live frames.

Build the native program with `-pthread`. Start `preview.py` with `--camera` to
let the two UI profile buttons manage its own exclusive camera child process;
it never terminates unrelated processes or loads an FPGA image. See `BOARD.md`.
