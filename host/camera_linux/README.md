# Z19 Linux camera 0 bench

This directory ports the already demonstrated FL0214/IMX214 camera-0 sequence
to Linux as a camera-only service. The unchanged hardware inputs,
reviewed bit/XSA and provenance are archived in
[camera_hw](../../fpga/camera_hw/README.md); external originals remain preserved.

The bench profile is tied to the previously tested four-camera XSA bitstream:

- bit SHA256: `28e1e3e7963ff12f57848998cf2695dcca139c3f519c5f020daf90dec4dc35ae`
- Bootgen raw bin SHA256: `e25e9bc7fd4c2008c7a198a91bc4937716b333259d08da7ed777d8ffe9b3384b`
- camera 0 VDMA: `0xA0060000`, scalar Digilent gamma: `0xA0040000`, reset GPIO: `0xA0080000`
- PS I2C0, `/dev/i2c-0`, sensor `0x10`, lens actuator `0x0c`
- PL clocks approximately 200/100 MHz; PS HP1 interface is 128 bits
- Linux `5.4.0-xilinx-v2020.2`, AArch64, GCC 9.2.0
- 1920×1080, BGR DMA bytes inferred from supplied RTL/XSA remap; three owned buffers (page-aligned stride 6221824)

The XSA has conflicting derived `C_NUM_FSTORES=6` and actual configurable
`c_num_fstores=3` values. The tested bit cycles indices 0/1/2. All six address
pairs are filled with aliases of allocated memory defensively; consumers use
only the three observed stores. Do not extrapolate this to another bitstream.

`sensor_table.h` preserves all 89 register/value entries from the tested
bare-metal `live_v2/src`; only trailing whitespace/newlines were normalized.
Original SHA256 `e4875d6bf8bec230e173ee97706837ea20d3d6a955f386069a39e48a509a2a5b`;
repository header SHA256 `136cffb7aedb45659e86a7abb5b5bcd2c772012e8177268d9348dbc857623ebf`.
The CSI source holds FIFO reset for 200 million byte-clock cycles and delays
writes for another 100 million. Capture waits up to 30 seconds for real frame
transitions, then begins measurement. A 500 ms delay was insufficient at first.

## Build on the board

The shipped kernel header tree lacks host tools and generated ARM wrappers.
Build an isolated copy, preserving `/lib/modules/.../build`:

```sh
export PATH=/usr/sbin:/usr/bin:/sbin:/bin
# Use a new, nonexistent destination; never overwrite an existing build tree.
cp -a /lib/modules/$(uname -r)/build /var/lib/amazinghand/build/kernel-camera-20261010
K=/var/lib/amazinghand/build/kernel-camera-20261010
make -C "$K" ARCH=arm64 CROSS_COMPILE= HOSTCC=gcc scripts
make -C "$K" ARCH=arm64 CROSS_COMPILE= HOSTCC=gcc asm-generic
make -C "$K" ARCH=arm64 CROSS_COMPILE= HOSTCC=gcc prepare0
cd /path/to/copied/camera_linux
make KERNEL_DIR="$K" module
make capture
```

Native syncconfig adds only `CONFIG_CC_CAN_LINK` and updates the compiler label;
it does not change the running kernel. The rebuilt module was actually loaded
and used to capture frames; vermagic alone is not the validation.

Convert a copy of the reviewed XSA's `design_1_wrapper.bit` with the existing
Bootgen, using a BIF containing `[destination_device=pl] camera.bit`:

```text
bootgen -image camera.bif -arch zynqmp -process_bitstream bin
```

Verify both hashes above, transfer the raw bin into `/lib/firmware`, then run
the guarded manual loader. It checks hashes, module ABI, active PL users,
clocks and the relevant PS interface registers before programming.

```sh
sh /opt/amazinghand/bin/load_z19_camera0.sh \
  /lib/firmware/amazinghand-camera-28e1e3e7-20261010.bin ./ah_camera0.ko
./capture_camera0 10 /var/lib/amazinghand/log/NEW_CAPTURE.raw 300
python3 test_device.py idle
python3 start_preview.py
```

On the directly connected PC, run `python host/camera_linux/view_camera.py`
and open `http://127.0.0.1:8766/`. This loopback viewer forwards only camera
HTTP routes directly to the board, preserving the PC's existing proxy settings.
Stop it with Ctrl+C. The board service remains available at
`http://YOUR_Z19_ADDRESS:9000/` when the browser can connect directly.

Preview now uses a persistent **1920×1080 MJPEG stream**, with no upscaling
from the old 320×180 image. A 30-second PC receive test decoded all 757 JPEGs
at 1920×1080, measured 25.161 frames/s, and found 757 different frames with
no missing published sequences. This measures received frames, not browser
rendering or lossless sensor acquisition. Actual rate depends on scene and
clients; the page displays the measured publishing rate and supports fullscreen.
Earlier 5 Hz snapshots and 320×180/29.4 Hz streaming are retained as history
in the bring-up log, not the current resolution.
Focus 0–1023 is a manual actuator position, not autofocus. No detection model
or robot-control process runs in this UI.
The helper detaches the server from SSH and prints a PID/log path; SIGTERM to
that verified PID stops the server. The capture also checks parent-process
liveness and stops if its server disappears. It is not an automatic boot service.
Four copy slices move the complete coherent DMA frame into ordinary RAM;
two native libjpeg-turbo workers encode BGR directly at quality 85. The board
already provides libjpeg-turbo 2.0.3 and development headers; no new packages
were installed. The Python server forwards encoded JPEGs without re-encoding.
Validate optical color against a known target; haze/focus is not resolved by
increasing resolution.

Copies begin just after a buffer transition. The complete status/copy/status
window must be at most 30 ms and the selected store must remain non-writable.
This bound is specific to the reviewed sensor profile, observed at ~55.6 Hz:
a complete overwrite and wrap requires at least two periods (~36 ms).
Do not reuse this bound for faster sensor modes. No mapping/cache properties
or driver ABI changed. Busy/unsafe/obsolete copies are discarded and counted;
JPEG workers only read cached copies. Metadata cannot regress in capture time.
Clients receive the newest published sequence without an application backlog.
A stale/error/stop closes an existing stream and rejects new frame requests.

Current deployment: `/opt/amazinghand/camera0-linux-hd-20261010`.
The old package is preserved. To run fault tests without overwriting prior
evidence, provide `python3 test_preview.py --output /path/to/NEW_RESULT.json`.
On the PC, `test_stream.py --seconds 30 --output NEW.json --snapshot NEW.jpg`
checks every received JPEG's resolution, sequence, capture time and delivery
intervals. It uses PC Pillow; do not install that dependency onto the board.
A separate 60-second HD run published 1666 frames without copy/busy/obsolete
discards, stopped DMA normally, joined workers and saved a 6220800-byte raw.
The service uses a one-hour capture session; press Start again after it ends.

## Ownership and shutdown

- One open owner; unknown ioctls, writable/partial/private/offset mappings are rejected.
- DMA buffers use `dma_alloc_coherent` and `dma_mmap_coherent`, limited below 4 GiB.
- File/VMA references prevent unloading the module while buffers are mapped.
- Normal stop: sensor stream off → VDMA halted → save stable previous store → unmap → close.
- Last file release, including process death, resets CSI and halts/resets VDMA.
- If hardware cannot halt, memory is retained, new opens are refused, and a
  critical message requires power-cycle recovery. It is never returned for reuse
  while DMA may still access it.
- Never reprogram PL with this module loaded. Stop the owned capture, check
  that the device is no longer open/mapped, then `rmmod ah_camera0` first.
- SD BOOT.BIN/FIT are unchanged. Reload this reviewed camera profile after a reboot before capturing.

Board results are recorded in [`docs/fpga/evidence/2026-10-10/`](../../docs/fpga/evidence/2026-10-10/README.md).
