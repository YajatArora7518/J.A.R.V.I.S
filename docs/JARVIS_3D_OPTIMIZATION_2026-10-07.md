# JARVIS 3D workflow repair — 2026-10-07

## UNDERSTANDING

The existing JARVIS-owned GLB studio works, but the actual Meshy Iron Man export
was subscription-gated after one expressly approved 20-credit generation. The
user has prohibited paid plans. The new service has not generated a GLB yet.
Graphify query traced the studio's command routing, attachments, local server,
renderer acknowledgement and Qt integration before changing their shared code.

## PLAN

Offer the researched free website route explicitly without buying anything or
claiming website opening generates a model. Fix concrete import verification,
reference metadata and unnecessary stationary GPU rendering issues. Reuse the
existing local server, renderer and import workflow without new dependencies.

## IMPLEMENTATION

- Primary “Try free on Tripo” button opens the allowlisted Tripo Studio URL in
  the existing Chrome profile. Meshy remains available for already generated
  assets with its observed paid-export warning. The viewer and spoken command
  response tell the user to check H2.5/free GLB export first and stop at an upgrade.
  Website generation and login remain service steps; this is not an automated
  generation API integration.
- [Official Tripo pricing](https://www.tripo3d.ai/pricing), checked 2026-10-07,
  lists 15 free exports for H2.5 only, public/non-commercial models. This is a
  published plan condition, not verified account eligibility or a promise of
  unlimited free models. Current pricing is linked beside the button.
- Import verification now tracks the specific imported content ID. Selecting
  another model cannot verify that import. Renderer failures clear stale
  acknowledgement and preserve RENDER_FAILED; displaced imports report
  IMPORTED_SUPERSEDED. READY appears only after the server accepts the rendered
  model acknowledgement, fixing a timing race found by the actual browser test.
- Invalid saved metadata and malformed/credential-bearing reference links are
  skipped without interrupting model loading. Arbitrary generator URLs remain
  blocked. Existing localhost token/origin/resource boundaries are preserved.
- Stationary scenes render only when changed; orbit, resize, movement, material
  changes, animation, auto rotation and returning to the visible page request
  rendering. Reset stops auto rotation. Obsolete parsed models and failed model
  resources are disposed; geometries/materials/textures are deduplicated during
  disposal. Failed imports clear the old preview and disable its controls.
- Website buttons suppress repeated clicks while their open request is running.
- Live GUI review exposed a naming ambiguity: the requested subject remained
  "ironman" after importing a robot sample. The sidebar now says REQUESTED SUBJECT
  and the canvas separately displays the actual GLB filename. Import does not
  guess identity/likeness from the request or relabel the sample.

## TESTS

- Initial sandbox run: 12 passed, 21 setup errors from restricted pytest temp
  directory creation. A workspace-temp retry encountered sandbox local-server/
  browser restrictions and was interrupted. These were not accepted passes.
- Installed-runtime scoped run: 32 passed, 1 failed. The failure exposed READY
  being shown before render acknowledgement; the implementation was corrected.
- Final local GLB/server/routing and isolated real Chrome renderer checks:
  **33 passed in 16.54s**. No user browser/profile was used by the test.
- After the live model-label correction, the same scoped checks passed again:
  **33 passed in 17.03s**, including requested Virat Kohli versus actual sample
  filename distinction. The total counts unique final checks, not repeated runs.
- The real official CC0 sample mesh was imported, orbited, zoomed, translated,
  switched between real and holographic materials, animated, paused and reset.
  After damping settled, the stationary 400 ms interval had **zero additional
  instrumented GPU mesh draw calls**. Broken reference entries did not prevent
  reimport/acknowledgement. This is a renderer workload check, not a whole-app
  CPU/battery benchmark.
- Related attachments, voice/chat routing, runtime recovery, natural replies,
  assistant repair, security confirmations, dashboard UI and prior optimization
  regressions: **257 passed in 12.44s**, two existing warnings (Google SDK
  deprecation and a legacy test returning a tuple).
- Total final passing checks: **290**. Scoped diff whitespace check passed.
- Graphify updated after the final changes: 5,066 nodes / 12,449 edges,
  AST-only, no API cost.
- Restarted only the task-owned JARVIS process after checking its executable and
  main.py path: PID 20184 → 4660. Startup reached “JARVIS RUNTIME FULLY READY”,
  registered all 73 tools. Charon Live fallback played the greeting and microphone
  capture resumed. Primary Google TTS still reported its existing 429 quota limit.
- Real updated JARVIS chat imported the labelled RobotExpressive sample through
  MODEL_3D and returned **verified=True**. The embedded studio displayed 19 mesh
  instances / 3,237 triangles / 14 animations and the new free-route button.
  Charon Live spoke the result. After final naming correction, restarted the
  same path-checked task instance again: PID 4660 → 3444.
- Final real GUI reopened the saved model with its explicit
  "GLB · RobotExpressive_sample.glb" caption and 19 mesh instances. Its
  “Try free on Tripo” button opened the real Tripo Studio page in the user's
  Chrome profile. The site is signed out and displayed the Google account chooser;
  no authentication dialog was automated. User handoff requested for sign-in.

## REVIEW

No subscription/payment/new generation was submitted in this repair round.
The generated grey Meshy Iron Man still needs a legitimate available export;
it has not been imported. No Tony Stark/Virat model or newly created animation
is claimed. Free Tripo account login, H2.5 selection, generation and download
still require a real end-to-end service test; its tab is now open for user login.
Actual user microphone recognition
was not independently retested; command routing and startup recovery were tested.

## FINAL

The JARVIS 3D workflow now prioritizes the free route, avoids false import success,
survives malformed reference metadata and reduces stationary rendering work.
The actual free generated Iron Man GLB remains outstanding; viewer tests use the
clearly labelled official CC0 RobotExpressive sample.
