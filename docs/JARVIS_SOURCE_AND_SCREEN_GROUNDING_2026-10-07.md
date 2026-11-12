# Source and screen accuracy repair — 7 October 2026

## Understanding

The old runtime accepted generic India search results for an India–New Zealand squad question. A Kohli century-count question could bypass search and use model memory. Screen analysis could capture JARVIS's own stale conversation and treat that conversation as proof about a hidden browser page. A five-second title cache did not distinguish changed pixels. Native voice could then paraphrase a correct tool result into a contradictory answer.

The existing Graphify architecture report and callers were consulted: intent router → shared command pipeline → registered search/screen handlers → UI and Live delivery. Existing provider routing, offline Windows OCR and Qt signals were reused. No new dependency was introduced in this repair.

## Plan and implementation

- Route volatile statistics, squads and current public roles to search. Recognize the user's Hindi screen request.
- Require several query-topic matches, fresh registered searches and actual readable source pages. Search results alone do not verify an answer.
- For cricket announcements/statistics, check live official news links and refine searches toward BCCI/ICC. Discover article links from public responses rather than storing answers or specific article URLs. Check the current official index even when search returns an older official article.
- Read at most five deduplicated pages, with three concurrent readers. Keep publication/update dates separate from retrieval time. Current answers require dated evidence within 31 days; missing, future or older dates are rejected.
- Select numbered passages taken from actual page text. Validate source IDs, passage IDs, quoted evidence and numeric values before composing the visible answer. An equivalent one-item passage-ID list is accepted; unknown, boolean or multiple IDs are rejected. Raw research input is excluded from conversation history.
- Supply natural Roman Hinglish answers, source links, source dates and check times. Unsupported evidence produces an explicit inability to verify; it does not deny that an event exists or invent a total.
- Preserve the checked reply through both shared commands and direct registered Live tools. Suppress contradictory generated audio/text and speak the approved result in the existing Charon voice. Do not execute a completed screen/search request again.
- On explicit screen analysis, briefly hide an active JARVIS window using its Qt thread, capture a fresh frame, then restore the window even after failure. Refuse an image whose target is still JARVIS's own window. Do not reuse a title-only cached observation.
- Keep text legible at up to 1920×1080. Cross-check visual quotes with existing offline Windows OCR, allowing common I/l/1 glyph confusion in words while keeping numeric checks. Reject unsupported denial words. Remove the fabricated confidence value of 1.0.
- Preserve cloud/local policy, sensitive-screen blocking, confirmations and existing microphone echo protection. Public webpage redirects are checked before fetching; private/local destinations are rejected.

## Tests

The final affected regression suite completed with **540 passed, 1 warning in 60.02 seconds**. It includes source/pixel evidence, native voice delivery, Live recovery, continuous conversation, task/check-in behavior, both real Qt WebChannel chat inputs, memory, browser/social routing and security confirmation. Tests use fake audio and mocked contact/power actions. The legacy WhatsApp launch test previously attempted to focus the real user's app and failed under that foreground state; it now checks desktop vs explicit-web routing and honest focus failure with mocked Windows boundaries.

Real public/source and supplied-image probes are stored in `scratch/source_grounding_probe.json` and `scratch/screen_grounding_probe.json`. The probe uses the exact user queries and the supplied BCCI screenshot, without live desktop capture, microphone input, audio playback or outgoing contact actions.

The supplied screenshot was independently OCR-read and analyzed by the configured vision provider. Its result identifies the 6 October announcement, Bhuvneshwar Kumar's inclusion and Shreyas Iyer as captain. A simulated JARVIS window target is rejected before sending an image to the vision provider.

Final public probes: the India–New Zealand query returned the complete 16-member squad from BCCI's 6 October announcement. The century-count query returned 55 from a dated 28 September page, consistent with the official ICC 30 September article read successfully in an earlier real probe. Repeated probes also exercised search variability and honest rejection: an older/historical source or a malformed evidence-ID shape could not be marked verified. The one-item evidence-ID shape was repaired and regression-tested; the final two exact queries both returned verified answers.

Supporting public pages: [BCCI announcement](https://www.bcci.tv/news/article/india-and-india-a-squads-for-new-zealand-tour-announced), [ICC dated milestone](https://www.icc-cricket.com/media-releases/kohli-closes-in-on-gill-at-top-of-icc-men-s-odi-batting-rankings), and [final count probe source](https://www.indiacricketschedule.com/2026/09/list-of-virat-kohli-odi-centuries.html). These are dated source results, not a promise about every subsequent match.

## Review and practical limits

These checks establish provenance and catch the reported stale-memory/self-chat failures. They are not a mathematical proof of semantic correctness. A recently modified historical article can still be unsuitable, and the model is instructed to reject that mismatch. The 31-day rule can withhold an otherwise valid older source. Search outages, unreadable pages, OCR errors or provider limits may produce an honest unverified response. No latest statistic is hardcoded.

The image probe verifies the supplied screenshot. Actual foreground-window hiding/restoration is covered with mocked captures; arbitrary live desktop contents were not captured by the repair tools. Physical microphone recognition and every external account action are not established by passing regression tests. The restart health check measures connection and audio-frame flow only.

## Final verification

The tested GUI was launched as process 22432 after the old project process was already gone. Only exact-project Python processes are eligible for the restart; other apps/accounts are preserved. Runtime health is recorded in `scratch/source_grounding_runtime_check.json`. Startup reached the ready state, Gemini Live connected and natural TTS received HTTP 200. The first frame sample preceded microphone warmup; it was repeated after the startup greeting/echo guard.

The repeated health check passed: correct current PID, fresh telemetry, connected session, capture enabled, increasing sent audio frames and zero send errors. This confirms runtime/audio flow, not recognition of a newly spoken command from the user.
