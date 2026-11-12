# JARVIS voice and call recovery — 7 October 2026

## Understanding

Real acceptance had succeeded for WhatsApp submission, the completed test call, Google contacts and JARVIS-owned YouTube playback. Two failures remained: dedicated Charon TTS returned HTTP 429 and an outgoing call popup was checked only once, half a second after the single click. The real YouTube reply also contained unnecessary whitespace from channel labels.

## Plan

Respect provider retry metadata, verify the already configured same-Charon Live audio route before enabling a backup, observe delayed call state without repeating the outgoing action, preserve exact numeric answers and test chat/voice consistency. No additional communications were authorized or performed in this round.

## Implementation

- Dedicated TTS now reads numeric/date `Retry-After`, Google `RetryInfo.retryDelay` and bounded `retry in ...` duration metadata. Repeated quota failures use bounded exponential cooldown when metadata is missing; delay is capped at 24 hours. Logs never print raw provider bodies or credentials. The UI explains a rate-limit wait if neither voice route can speak.
- A real reply-only probe of Charon Live generated audio successfully before enabling `natural_voice_live_fallback` in runtime settings. TTS and Live use separate cooldowns and existing bounded audio caches. The backup uses the configured Google Live model and Charon voice, sends only the reply text and constant pronunciation instructions, and has no tools, screen, contacts or memory. Cloud-policy and natural-voice opt-in checks remain.
- Backup is skipped after any partial TTS playback or cancellation. A failing Live route enters its own cooldown; it cannot loop or keep retrying the primary quota-limited TTS route. Windows robotic fallback remains disabled.
- Outgoing native icon-call verification polls up to four observations, checking the selected recipient and a separate call popup with pending status or a duration counter. It clicks exactly once. Ordinary chat timestamps or another recipient cannot prove call success. Each OCR operation retains its existing timeout; the five-second poll deadline does not preempt an OCR operation already running.
- YouTube card title/channel whitespace is normalized before display and speech.
- Verified numeric calculator replies now display and speak `Iska jawab 221 hai, bhai.` while preserving the result value. Unverified or unrelated text is unchanged.

## Tests

- Added 16 isolated regression cases in `tests/test_voice_call_recovery.py`: server delays, malformed metadata, cooldown/no repeated provider request, no robotic fallback, delayed popup/other-recipient/chat-timestamp rejection, one-click guarantee, same-Charon reply-only backup, partial-speech suppression, backup cache and independent failure cooldown, YouTube whitespace.
- Focused voice/call/media/continuity suite: **139 passed, 1 warning, 10.33 seconds**.
- Broader affected regression suite: **381 passed, 1 warning, 26.21 seconds**, including voice/chat, runtime glitches, contacts/documents/media, WhatsApp/social mocks, web/source grounding, optimization and confirmation behavior. This run preceded the final numeric presentation adjustment.
- After the presentation adjustment, chat/voice parity expectations were updated to the intended Hinglish output. Final affected checks: **102 passed, 1 warning, 11.15 seconds**.
- Changed modules and test files compiled; scoped whitespace check passed. Graphify AST update completed with **4,984 nodes / 12,300 edges**, curated graph backed up. Final refresh detected no further code-graph changes. No new dependency or LLM clustering call.

### Real provider and app acceptance

1. Dedicated TTS probe: HTTP 429, **37,075-second retry delay**, no audio, 2.26 seconds elapsed. Only constant `Haan, bolo.` text was sent. This confirmed a long provider cooldown, not a local microphone failure.
2. Same Charon Live probe: **63,360 audio bytes**, 7.69 seconds total including speech/cleanup; audio generation succeeded. This is a single sample, not a general latency benchmark or exact voice-quality guarantee.
3. Updated app startup used the actual output stream and logged `Reply played using configured Live voice (Charon)`; microphone capture resumed afterward.
4. JARVIS's visible command field accepted `calculate 13 * 17`. Before the wording adjustment, it displayed 221 and completed Charon Live playback. The final version displayed `Iska jawab 221 hai, bhai.` and logged completed playback using configured Live voice (Charon), followed by resumed microphone capture. No additional dedicated TTS request was made for this command during the primary cooldown.
5. The final interactive app is PID **7088**, with a visible JARVIS dashboard. Earlier background-only/test processes were stopped by exact project/PID match. Other apps were preserved.

Evidence: `scratch/voice_quota_probe_20261007.json`, `scratch/voice_live_probe_20261007.json`, `scratch/voice_live_probe_20261007.wav`, and `scratch/recovery_final_20261007.*` logs. Existing saved contacts were not rewritten by this round.

## Review

The underlying dedicated TTS quota remains controlled by Google. The working Live backup restores speech for the tested replies while that quota is exhausted; it can itself fail or be rate limited, in which case the reply remains visible. Named Charon voices across Live and dedicated TTS may differ slightly in delivery; exact recitation is more strongly supported by dedicated TTS. Google's documentation distinguishes these routes: [speech generation](https://ai.google.dev/gemini-api/docs/speech-generation), [API errors](https://ai.google.dev/gemini-api/docs/api-errors).

No second Divyansh call or message was made. The delayed-call repair has synthetic regression evidence; it is not being relabelled as another real-call acceptance. Actual human microphone recognition and the user's assessment of naturalness still require their own spoken input; transport health alone does not prove those.

## Final

Same-Charon fallback speech is now available during the observed dedicated TTS quota failure. Call verification tolerates a delayed popup while retaining one attempt and recipient checks. YouTube labels and calculation wording are cleaner. The final app remains open and the remaining provider and live-call acceptance limits are stated explicitly.

Final runtime snapshot: PID 7088, `Responding=True`, JARVIS dashboard title present, session connected, microphone enabled/unmuted, capture enabled, speech finished, 1,842 audio frames sent, zero send errors, zero dropped frames and zero reconnects. No recognized human speech was included in this snapshot; it does not prove user-microphone command acceptance.
