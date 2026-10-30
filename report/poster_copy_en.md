# English poster copy — Xinyu SmartSort

Content draft for the required one-page final-round poster. The official AMD PPT template has not been supplied; no template-based PPT or print-ready poster has been created. After receiving it, place this copy into that template, omit team/institution information, and prepare the required A4 colour print. Rule provenance: [requirements map](../docs/competition/requirements_map.md), PDF physical page 28 / printed page 25.

## Title

**Xinyu SmartSort**

**A Voice–Vision Waste Sorting System Based on Zynq Hardware–Software Co-design**

*Hear the command. See the target. Put sorting into action.*

## Need and use

A tabletop workstation that makes a sorting task understandable: one wake/start interaction, visual recognition, spoken category feedback, and a visible pick-and-place sequence. Target uses include environmental education, embedded-system teaching and FPGA prototyping.

## User journey

**Wake → Start → Prepare → Recognize → Announce → Pick and place → Wait for a new wake.**

Busy commands do not queue a second action. The arm uses a fixed pickup position and existing category actions.

## Z19 source architecture

**USB camera → PS capture/decode → AXI-Lite FIFO PIO → PL video processing → PS CPU detector and coordinates → PL candidate rules → VM task, announcement and SDK.**

**USB microphone PCM → PS ALSA → PL audio filtering → PS Vosk → restricted task events.**

| Function | Programmable logic | Processing system |
|---|---|---|
| Video preprocessing | Channel gain/bias, HSV and mask | Capture, decode and complete PIO readback |
| Waste recognition | Processed pixels and candidate rules | Real CPU YOLO adapter and category mapping |
| Visual location | ROI count, bounding box and first moments | Box recovery, centroid and optional planar mapping |
| Audio preprocessing | DC blocker, 63-tap FIR and optional soft gate | USB PCM, configuration, Vosk and task commands |

## Engineering contribution

Frame-bound configuration, backpressure, fixed-point saturation and consistent register contracts; one-shot task permits; source/session/frame tracking; read-only previews and traceable task records. The default semantic-box policy does not require a particular object colour.

## Evidence and configuration

The existing VM demonstration and standalone Z19 colour pipeline have their own recorded results. The integrated four-function profile is a source delivery; it has no new combined board measurement. Numeric results and resource reports remain in the [versioned evidence matrix](../docs/competition/EVIDENCE_MATRIX.md).

Demonstration scope: a single object at a fixed pickup station. Object material coverage is not characterized. Planar coordinates require matching calibration. SDK completion is not physical-grasp confirmation. The read-only camera preview is raw PS capture, labelled `pl_processed=false`.

## Reuse and attribution

Reusable Skills cover stream/frame contracts, register contracts, voice task boundaries and read-only observability. Vendor models, SDKs and existing actions retain their provenance; the HSV arithmetic retains its MIT notice. Engineering source and versioned evidence accompany the submission.

## Asset placement notes — not poster-body copy

| Poster area | Existing material | Caption/handling |
|---|---|---|
| Main workstation/UI image | [Real VM dashboard](../docs/assets/dashboard.png) | Existing VM/DOFBOT configuration; not a new PS/PL integrated measurement. Inspect the original-resolution material and remove any team-identifying content before final template placement |
| Product workflow | [Design report, Figure 2](design_report.md#section-principle) | Functional concept, including an optional PS/PL configuration |
| Technical architecture | [Design report, Figure 4](design_report.md#section-principle) | Source-profile connections; CPU inference and PIO explicitly labelled |
| Prior board evidence | [Evidence matrix](../docs/competition/EVIDENCE_MATRIX.md) and linked original colour records | Retain original profile, resolution and measurement scope; copy no unqualified headline figure |
| Physical workstation photo | Only an existing, source-identified photo of this project | No stock industrial-sorting image, synthetic device photo or invented operating scene; suitable full-device material still requires selection |
| Reproduction/Skill access | [System source entry](../fpga/system_pspl/README.md), [Skill index](../skill/README.md), [submission manifest](../deliverables/submission/manifest.json) | Use the actual submitted revision; any printed URL/QR must also pass the poster anonymity check, with no team/account identifiers |

The body is intentionally a copy bank rather than an official layout. The final template may require further shortening; all version and evidence qualifiers must remain attached to their claims.
