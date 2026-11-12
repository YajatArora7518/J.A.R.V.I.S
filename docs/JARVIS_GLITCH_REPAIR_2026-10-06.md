# Runtime repair and optimization — 6 October 2026

## Observed problems and resulting behavior

The Live receive loop previously treated any generated voice acknowledgement as handling a command. A model saying “opened” without calling `assistant_command` could therefore suppress the actual laptop action. Known action requests now suppress such output and route once through the shared command pipeline. An attempted command is never automatically retried, including a failed or uncertain send/call. An unverified tool response replaces the model's spoken claim with its actual result. Conversation audio remains native. Intent is recomputed only on new transcript text, rather than every audio packet.

The watchdog could clear speaking after fifteen seconds or two seconds without Live packets while the independent speech engine was still generating/playing. Speaking state now remains owned by active TTS, queued audio or an ongoing device write; the watchdog only recovers an actually idle state. Explicit stop can force release. Live and cached/generated speech use writes of at most fifty milliseconds of PCM, with cancellation checks between writes.

The speech worker could clear a stop flag after dequeuing an old job, or enter Windows fallback at the same time stop arrived. Queue generations invalidate old jobs. A stopped reply does not fall through to Windows speech, and a fresh identical request after stop is accepted. Fully completed short natural replies are cached in process memory only: up to twelve entries, one MiB total, and 256 KiB per reply. Partial, failed and cancelled replies are excluded; voice/model/text form the cache identity. Cached replies require no new provider request. Existing cloud opt-in and policy checks remain in place.

The dashboard now limits idle/listening animation to thirty frames per second, while speaking/thinking/executing can render sixty. Pixel ratio is capped at 1.5; hidden legacy ring/satellite/canvas animation work is skipped. Existing controls, reactor visuals and API compatibility are retained.

An actual cold Discord launch exposed another bug: the visible Discord Updater was counted as the main app. Launch verification now requires a visible window owned by the exact app process, excluding its updater/setup/loading windows. Already-ready windows do not incur the old fixed 1.2-second sleep. Startup is polled for a bounded period; an updater-only state is reported as pending readiness and does not trigger another launch. Foreground verification is still required. A browser mentioning the app or only a background process is insufficient.

The running cloud session produced a provider 1011 internal error and subsequently reconnected. The repair retains bounded reconnection, counts failures accurately, and prevents an immediately failing socket from resetting the retry budget forever. A session must survive thirty seconds before it resets that budget; three consecutive failures fall through to the existing local speech path. Startup/reconnect UI status also preserves active speech rather than incorrectly showing LISTENING over it. Provider availability and local recognizer readiness still matter.

## Executed checks

Two further runtime observations were repaired: voice `You:` transcripts now appear in the conversation panel, while the typed input path still renders each user bubble once. The isolated production Qt/WebChannel check verifies both paths. Missing local Ollama previously spawned/logged another recovery every health poll. Recovery now reserves its worker atomically and waits five minutes between failed attempts, while health checks continue to detect a manually restored server immediately. An unavailable provider is not reported as online just because its first failed check was labelled degraded. The monitor also stops promptly.

Final affected regression suite: **387 passed, 2 warnings, 66.76 seconds**. Files: `test_runtime_glitches`, `test_daily_companion`, `test_reference_upgrade`, `test_voice_chat_parity`, `test_assistant_repair`, `test_natural_reply_voice`, `test_dashboard_acceptance`, `test_assistant_controls`, `test_extended_assistant_controls`, `test_social_chat_browser`, `test_whatsapp_production_upgrade`, `test_security_confirmation`, `test_holographic_ui_replacement`, plus `scripts/test_proactive_assistant.py`. External messages/calls, provider calls, destructive actions and sound devices were mocked or isolated fixtures.

New regression probes include phantom app/message/screen/power/calculation acknowledgements, one attempt even on unverified results, memory saving not counting as an app launch, ordinary conversation preservation, no reclassification per audio packet, watchdog ownership, turn completion before audio finishes, cancelled queue generations, the cloud/Windows fallback cancellation boundary, fresh requests after stop, completed-only caching and large-packet cancellation.

Actual local HTML/Three rendering passed at **1440×900** and **1100×700** with no page errors or out-of-bounds controls. The headless measurement observed **28 listening frames** and **59 speaking frames** over about one second each; this is a rendering budget check, not a measured whole-laptop CPU or battery improvement. Actual Qt WebChannel verification also passed through the production dashboard using two arithmetic commands and temporary local planning data, exactly once each. Evidence: `scratch/reference_ui_20261006/report.json` and `scratch/dashboard_bridge_check.json`.

## Final running build evidence

The complete patched app was restarted as PID 3332. Its current microphone health file showed an active cloud connection, audio frames sent, zero send errors and zero dropped frames. Actual spoken exchanges had also been observed on the preceding repair build; every physical utterance on the final build has not been acceptance-tested.

Using the visible production JARVIS command field, `open Discord` was entered and submitted once. Correlation `CID-823999` reached `open_app`, returned `success=True, verified=True`, and the independently enumerated app window was `Friends - Discord`. This final test focused an already-running main app; the earlier cold-start updater issue is covered by the new regression probes. No account message/call was sent. Evidence is saved in `scratch/glitch_repair_runtime_check.json` and `scratch/glitch_repair_complete_20261006.stderr.log`.

The real Charon speech request for “Opened Discord” timed out, and the existing Windows speech fallback ran. That cloud provider dependency remains; this repair cannot claim that all replies now sound natural or that provider delays are eliminated. Local recovery log flooding was absent in the captured new build interval.

## Practical limits

The update does not establish that all laptop/account tasks or every physical microphone utterance work. Unknown commands still need an actual supported capability; login, OS permissions, provider outages, app layouts and recipient resolution remain real dependencies. Existing action confirmations and protected paths are retained. No new contact was messaged/called, no real shutdown/restart of Windows was performed, and no timetable was supplied or inferred in this repair. The app process itself was restarted to load the fixes.
