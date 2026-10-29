# Repository working rules

## Active scope

The active project and only GitHub write target is **Citlali6/VisionGrasp-Z19**. Maintain the verified DOFBOT voice/vision sorting application, the Z19 FPGA perception chain, and the separate candidate-guard engineering work. Existing hardware demos remain independent until a joint integration is actually verified. Read [architecture](docs/ARCHITECTURE.md), [development](docs/DEVELOPMENT.md), [validation](docs/VALIDATION.md) and the relevant module README before editing.

The DOFBOT demo uses fixed pickup coordinates. Preserve its verified wake/start semantics, classification-audio-before-grasp ordering (the existing observation preparation may move before recognition), motion parameters, detector conditions, UI and startup interface unless the user requests a behavior change. FPGA perception and the new `sort_guard` do not currently control DOFBOT. The guard consumes candidate statistics through PS-validated metadata and an explicit AXI register interface; it does not implement garbage semantics, image denoising, or a certified safety interlock. Documentation must distinguish software checks, command completion, user observations and independently measured physical performance.

## Preserve work and use Pull Requests

Before edits, inspect `git status`, `git branch --show-current` and `git remote get-url origin`. Work on a named branch based on the latest remote `main`; do not edit or commit on `main`. If another checkout contains uncommitted work, preserve it and use a separate worktree. Do not automatically stash, discard, reset or mix unrelated changes.

Follow [Git workflow](docs/GIT_WORKFLOW.md): focused branch → checks and diff review → commits → branch push → PR → authorized merge. Never push directly to `main`, force-push, rewrite history, bypass hooks or silently alter branch protection. Do not automatically remove branches; branch archival or deletion is allowed only within an explicitly authorized scope after preserving commits, references, worktrees and uncommitted work. Activate `.githooks` in the local clone. Review the diff and applicable checks before merging. Another person's approval is optional under the owner's policy, but actual GitHub protection still applies; never report an approval that did not occur.

Commit, push and merge only within the user's authorized task. Authorization already given for the current task remains valid; do not ask repeatedly for the same step. Do not write to upstream source repositories, including `Tom-mr33/AmazingHand-based-on-FPGA`; these are read-only provenance sources.

## Hardware and deployment

Repository work and CI default to offline tests with mocked devices. Do not open real serial ports, send actuator commands, load FPGA images, probe unknown MMIO, write SD cards or restart a deployed demo without task-specific authorization. A previous test or log is not authorization for a new hardware action.

Repository packaging does not require replacing the running virtual-machine application. Use the installer's isolated staging mode to verify generated scripts. Keep generated builds and runtime data outside source directories. Preserve required source, constraints, Tcl, BD/IP configuration and validated manifests; do not blindly edit generated IP or upgrade the camera project to another Vivado version.

## Attribution and release quality

Root Apache-2.0 applies to project-authored code; third-party material retains its own notices and licenses. Follow [THIRD_PARTY.md](THIRD_PARTY.md). Do not attribute detector weights, vendor SDKs, existing motion routines or upstream IP to the team. Keep compatibility device/module/deployment names where required by an existing ABI.

Competition materials must separate current hardware observations, software tests, RTL simulation and synthesis. Keep unsupported performance values marked as unmeasured; preserve template anonymity and attribution requirements. Do not turn planned cooperation into a completed hardware claim.

Before submitting, run the relevant offline checks, inspect new files and staged diffs, check links and source references, and report unavailable checks honestly. Do not publish credentials, helper scripts containing credentials, personal path inventories, runtime logs, full VMs or restricted model/audio packages. Keep commits focused and explain the resulting behavior and verification.
