# JARVIS voice and search recovery — 2026-10-07

## UNDERSTANDING

The user put GLB/3D work on hold and requested remaining bug fixes. The existing voice/chat pipeline and source-grounded search were retained. Graphify was consulted before cross-file changes.

Failure injection reproduced 10 failing cases out of 12 initial probes:

- A completed voice tool could lose its spoken result if receiving or sending its Live response failed, or the socket was already closed. The closed/send path continued waiting instead of immediately renewing the session.
- An unexpected speech synthesis exception left an unfinished queue item, despite processing subsequent replies.
- Source synthesis/checker exceptions and null responses escaped structured error handling. Null claim text could become the literal string `None` and pass verification.
- Failed HTTP status checks or streamed reads did not close the response.

## PLAN

Repair the shared boundaries with the existing runtime and libraries. Preserve source verification, action deduplication, user interruption and explicit silence. Verify failures synthetically, run related regressions, review, refresh the local graph and restart only this task's JARVIS instance.

## IMPLEMENTATION

- `main.py`: retain the actual completed tool result for disconnect recovery. Queue that result for speech only when no reply audio was accepted; never execute the tool again. Clear saved replies on interruption and completed turns. Failed tool response delivery immediately requests session renewal. Cancellation and silent results do not trigger recovery speech.
- `core/tts_engine.py`: balance each dequeued item with exactly one `task_done()` in `finally`, including exceptions, skipped generations and the shutdown sentinel.
- `actions/web_research.py`: contain synthesis/checker provider failures, reject null/non-dictionary responses and non-string claim/quote values, and return the existing authoritative `WEB_ANSWER_UNVERIFIED` result when verification cannot finish.
- `actions/fetch_webpage.py`: close HTTP responses on status/stream failures as well as normal reads and redirects.
- Added `tests/test_non3d_recovery.py`. Updated the existing failed-send session test to require immediate renewal while still asserting one tool execution and clearing the pre-action resume token.

No dependencies, account settings, paid services or 3D features changed.

## TESTS

Executed with the installed Python 3.14 runtime and workspace-local pytest temporary directories:

1. Initial failure injection: **10 failed, 2 passed**.
2. After patching the four shared boundaries: **12 passed**.
3. Broader regression selection: **386 passed, 3 failed** across 389 cases. The failures were the old delayed-cancellation expectation and two UI timeouts.
4. Targeted recheck: **4 passed**, covering immediate renewal, both dashboard input boxes and the actual isolated Qt/WebChannel bridge. No production UI change was needed for the transient timeouts.
5. Final recovery/session selection, including five additional silence/interruption/malformed-response cases: **46 passed**.

Across these runs, all **394 unique selected cases** passed on their final relevant execution. This is a cumulative result, not a single 394-case all-green run. The broader selection covered voice/chat parity, session continuity, natural reply speech, source grounding, webpage reliability, study/contact routing, security confirmations, application focus verification and dashboard rendering.

The actual isolated Qt bridge used the production command pipeline and verified arithmetic results (221, 899 and a two-step calculation), one dispatch per submitted command, one user/answer bubble, working-state entries, Talk-button behavior and temporary planner persistence. Speech was mocked in that test; contacts and messages were fixtures.

Graphify AST update completed without LLM/API use: **5,076 nodes, 12,490 edges**.

Restarted only the command-line-verified task-owned JARVIS instance: PID 3444 to 30840. Host process verification reported a responding `J.A.R.V.I.S — Futuristic AI Command Center` window. Startup logs showed 73 registered tools, DuckDuckGo search fallback ready, runtime initialized, Windows mic unmuted, and configured Live/Charon greeting playback. Mic capture returned to enabled after speech. Final logs confirmed Live connected on attempt 1, the Realtek microphone stream opened, and receive/play loops started. The primary Google TTS request returned HTTP 429; its existing quota cooldown and Charon fallback remain active.

Existing warnings: Google SDK Python deprecation; one legacy security test returns a tuple rather than `None`.

## REVIEW

- Network failures were simulated rather than deliberately disconnecting the user's laptop.
- Accepted audio suppresses duplicate fallback speech; this cannot prove that every accepted audio packet was physically heard before a device/connection fault.
- Real microphone recognition and full end-to-end speech reliability require use on the laptop. Unit and bridge checks do not establish 100% hardware reliability.
- Existing Google TTS quota limits remain external constraints. The configured Live/Charon fallback is retained; this change does not remove provider rate limits or guarantee current web facts when sources cannot be verified.
- No real messages or calls were sent in this round. No new search fact or squad/statistic was asserted from test fixtures.
- GLB generation, website authentication and importing remain on hold.

## FINAL

The reproduced disconnect reply-loss, TTS queue-accounting, malformed search/provider failure and HTTP-response cleanup bugs are fixed. Related selected checks pass after the targeted rechecks. The task-owned JARVIS was restarted with these fixes and its responding window, search startup and Charon greeting playback verified.
