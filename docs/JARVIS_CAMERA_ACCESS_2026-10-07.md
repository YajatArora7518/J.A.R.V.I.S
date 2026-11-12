# Camera and honest laptop access — 7 October 2026

## Understanding

The user requested usable camera access and broad laptop controls. The existing camera tool only changed a boolean and announced activation without checking hardware. Its analysis branch discarded the actual observation and returned “Analyzing camera feed.” The Camera button similarly changed its badge before checking hardware. The existing Graphify report and the command pipeline, tool registry, camera provider, permissions, capture helper and Qt callbacks were inspected before changing this flow.

Actual camera observations are limited to visible objects/actions. Facial emotion/mood inference remains excluded; neutral check-ins and user-reported feelings are supported. A registered tool cannot manufacture OS administrator rights or account login.

## Plan

Reuse fresh capture and the existing command/tool pipeline. Verify hardware before camera readiness, preserve the actual analysis result, expose real capability status, and keep camera controls safe across worker/UI threads. Preserve existing confirmations, research checks and gesture functionality.

## Implementation

- New `actions/camera_control.py` verifies a local frame on `camera on`, immediately releases it, then saves on-demand access. It uploads/stores no camera image for that check. Off disables the existing provider and clears the saved access; status distinguishes saved access from hardware checked this session. Analysis returns the existing source-checked vision result unchanged.
- Camera controls and `access status` have exact shared voice/chat routing. The tool registry uses the real handler rather than a pretend activation acknowledgement. `actions/assistant_access.py` reports registered tool names, actual process admin state, camera preference and cloud policy. It does not probe accounts, grant admin rights or weaken confirmations.
- Permission writes preserve unrelated settings, are atomic/locked, and roll back on failure rather than claiming success. Corrupt configuration is preserved.
- Camera button dispatches commands; UI state updates only from the result, through a Qt signal. The existing hand tracker remains available on a separate explicit Controls button, with start/stop gating; it is no longer implicitly started by enabling on-demand observation.
- Direct camera observation obeys privacy pause. Hardware releases even if opening/reading fails.
- Real testing exposed a separate cause: the camera autodetection diagnostic contained an emoji that raised `UnicodeEncodeError` in the Windows legacy console before any device access. Camera diagnostics are now ASCII. Detection accepts a real valid frame, never saves a guessed device index, and saves the index in non-secret runtime preferences while leaving the API credential file untouched.

## Tests

- Initial isolated camera/companion/source/planner/dashboard/control tests: **162 passed**, one warning, 19.61 seconds.
- Broad affected regression suite: **601 passed**, one warning, 68.58 seconds. Same affected suite as the companion report, plus `tests/test_camera_access.py`; no real sends/calls/power actions or camera frames in these tests.
- After the observed console bug and camera-selection fix: **247 passed**, one warning, 18.03 seconds across camera access, companion banter, source grounding, daily companion, dashboard acceptance, assistant controls, holographic UI and voice/chat parity.
- Final callback tests: **17 passed**, 1.08 seconds. After preserving the explicit hand-tracking control: **38 passed**, 11.03 seconds across camera access, holographic UI and dashboard acceptance. The broad suite was not repeated after these localized changes.
- Real local hardware probe initially failed due to the console encoding exception. Windows Integrated Camera status was OK and Windows user/machine/desktop webcam permissions were already Allow. After the fix, camera index **0** provided a valid **20,662-byte** frame; capture was released and only readiness metadata saved. `camera_permission=true`, `continuous_capture=false`, `cloud_upload=false`. No facial mood analysis, photo retention or cloud camera test was performed.
- Actual capability inventory: **70** registered tools, current process `windows_admin=false`, cloud policy allowed. Account authentication was not probed. This demonstrates availability/status, not completion of every possible laptop action.
- Targeted whitespace review passed.
- Restarted app PID **17428** was responsive; Live stayed connected, microphone frames sent increased **956 → 1036**, with **zero send errors**. Capture was enabled in the first two samples and temporarily paused in the last sample by the existing speaker/echo gate.

Evidence: `scratch/probe_camera_readiness_20261007.json`; restarted runtime logs and health samples are in `scratch/camera_access_20261007.*` and `scratch/camera_access_runtime_check_20261007.json`.

## Review

Future camera/vision requests can still fail if another consumer holds the device, the camera shutter/driver changes, OS permissions change, or the provider is unavailable. Gesture tracking owns a camera stream and may conflict with a fresh capture. Camera access enables explicit observations, not continuous surveillance. Source verification and disruptive-operation confirmations are unchanged. Protected OS changes and service accounts still require their real permissions; the assistant does not claim blanket administrator access. End-to-end cloud vision on the user's live camera and every desktop/account action were not tested in this turn.

## Final

Real camera readiness passed and on-demand camera access is enabled. Camera and capability controls now give actual results through voice/chat, with honest limits and persistent settings.
