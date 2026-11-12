# Session continuity repair — 6 October 2026

## Understanding and plan

The previous build sustained voice conversations but refreshed typed context only when rebuilding the Live session. It also treated waiting for TTS generation as speaker playback, closing the microphone during that wait. Paused sequences returned their remaining steps without associating those steps with the exact later confirmation. This update extends the existing history, command pipeline, power confirmation and speech engine.

## Implementation

Typed replies advance a local context revision. If Live has older context, the next voiced question is required to reach the shared command pipeline; stale native audio/text is suppressed. The current question retrieves the existing redacted, bounded history. Earlier typed commands are never resubmitted as new actions. A verified Live tool answer consumes that revision because its returned answer becomes part of Live history. If no tool is used, the shared pipeline supplies the answer; context routing stays pending until Live has an actual shared-context result or its configuration is rebuilt. An empty standalone wake is still acknowledged normally. Chat/voice continue to use Charon.

TTS now distinguishes waiting/generation from actual sound playback. Microphone capture is permitted while a reply is being generated, preserving mute/device controls and the existing echo tail. Actual TTS playback still closes the speaker microphone gate. New addressed input cancels a queued/generating reply that has not begun playback. Stop cancellation remains bounded by short audio writes, and incomplete/cancelled speech is not cached. Health snapshots expose `tts_generating` and `tts_playing`, never raw recordings or transcript content.

Sequences awaiting the existing voice/chat power confirmation retain an exact confirmation ID, a thirty-second deadline, completed steps and remaining commands in process memory. A matching confirmation result resumes only remaining commands after success **and verification**; previous verified commands are not repeated. Cancel, expiry, a different request ID, a new request, failure or uncertain execution discards continuation. A second confirmation-required step receives its own request ID. This is not a generic approval grant and does not bypass any registered tool's security gate. A pending power cancel takes priority over stopping speech so `cancel` really cancels that request. New requests invalidate old approvals even if they return early through memory/daily features.

## Tests

Focused suite: **160 passed, 1 warning**. Final affected eighteen-file regression suite: **445 passed, 2 warnings in 61.54 seconds**. Includes voice/chat context, speech ownership/cancellation, exact confirmation continuation, payload integrity, daily companion, actual isolated Qt/WebChannel, social controls, memory, adaptive context and security checks. Tests verify shared chat/voice resolution, one confirmed attempt, no replay of earlier steps, cancel/expiry/unverified/mismatched-ID rejection, microphone generation versus playback behavior and actual sound-write state transitions.

All Windows power operations in these tests were mocked. No contact was messaged/called. Qt acceptance uses an unshown production window and temporary planner data; actual physical multi-turn speech is distinct from synthetic packet coverage.

The final patched app was restarted as PID 35308. Three fresh health samples confirmed a connected Live session, enabled microphone capture, increasing sent audio frames (2125 at the final sample) and zero send errors. Startup Charon TTS returned HTTP 200; runtime logs show capture closing for playback and resuming afterward. Evidence is saved in `scratch/session_continuity_runtime_check.json`. This checks actual startup speech service and microphone transport, not the user's physical multi-turn recognition accuracy.

## Review and practical limits

Continuation currently binds to the existing non-blocking power confirmation path. Other high-risk tools retain their existing security dialog/callback. Real Windows shutdown/restart acknowledgement is intentionally unverified; its remaining sequence steps therefore do not automatically run merely because Windows accepted the request. Speaker playback interruption still needs the appropriate headphone/barge-in configuration or the independent chat stop control. This update improves listening during generation, not acoustic echo cancellation or speaker identity recognition. Cloud speech/text latency and provider outages remain possible. No timetable or new check-in schedule was added.
