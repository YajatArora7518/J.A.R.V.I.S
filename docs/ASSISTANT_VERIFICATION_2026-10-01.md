# JARVIS verification — 1 October 2026

This extends `ASSISTANT_REPAIR_2026-09-30.md`. Existing unrelated edits were preserved. The Graphify report and the actual voice → command pipeline → registry → native/browser executor paths were reviewed.

## Changes

- Explicit WhatsApp sends preserve the exact contact/message and reach the native executor once. Registry wrappers now forward strict Boolean confirmation flags. Reply uses the same guarded send path. High-risk registry security checks remain in place.
- Current WhatsApp Web search inputs, conversation headers, composers, visible messages and outgoing sent ticks are supported alongside the older layout. Existing drafts are preserved; uncertain sends are not repeated.
- Native call controls use app-owned accessibility when available, then a unique observed phone glyph and offline call-state OCR. Answer/end controls require an incoming/active call window and recheck its ownership, foreground and bounds. An uncertain action never retries through another backend. Browser fallback requires an existing authenticated session.
- Broken cloud audio dispatch now exits immediately so the existing reconnect loop can recover, instead of repeatedly dropping frames on a closed stream.
- Browser connections are reused. Account discovery checks actual existing sign-in controls and does not equate installation with login or an installed ADB executable with a connected phone.
- Notification aggregation accepts captured events, deduplicates atomically and bounds storage. Visible chat messages are not falsely reported as new unread notifications. A disconnected notification source reports unavailable access.
- Unsupported social operations report failure. Implemented Instagram Like and YouTube play/pause require an unambiguous target and verify resulting state; playback requests are idempotent.
- SMS opens a quoted Android draft and explicitly does not claim delivery. Disconnected SMS/call-log access reports failure.
- Reminder delivery now finishes its spoken sentence and uses a native notification with a 15-second timeout. The indefinite dialog fallback was removed after the first actual delivery test failed to finish.

## Executed tests

Final affected suite:

```text
python -m pytest tests/test_assistant_repair.py tests/test_assistant_controls.py tests/test_social_chat_browser.py tests/test_security_confirmation.py tests/test_extended_assistant_controls.py tests/test_extended_browser_controls.py tests/test_assistant_api_controls.py tests/test_web_search.py -q --disable-warnings -p no:cacheprovider
141 passed, 2 dependency warnings, 30.30 seconds (final call-state review run)
```

Additional memory/adaptive/UI suite executed earlier in this audit:

```text
python -m pytest tests/test_contextual_adaptive.py tests/test_predictive_adaptive.py tests/test_adaptive_intelligence.py tests/test_holographic_ui_replacement.py tests/test_holographic_hud.py tests/test_holographic_info_hud.py -q --disable-warnings -p no:cacheprovider
124 passed, 22.22 seconds
```

**265 distinct test cases passed across these two suites.** Browser communication tests use isolated Chrome pages with all URLs intercepted. API commands use a fake assistant. No test fixture sent real account messages, placed real account calls or liked real posts. Search coverage includes a read-only live provider check; its test permits empty results and does not prove all providers are available. Syntax compilation also passed for 38 relevant Python files. A targeted whitespace check passed for the reviewed control files; unrelated pre-existing formatting changes were preserved.

## Actual laptop checks

| Feature | Observed result |
| --- | --- |
| Divyansh WhatsApp test call | One user-authorized native voice call was placed using the computer-use skill. A duration counter confirmed connection; later the chat showed a completed **2-minute voice call**. The floating call popup could not be targeted to hang up through that control tool. No second call was placed. |
| Reminder delivery | First test ran but failed to finish, prompting the fix. Second uniquely owned test reminder ran and completed with Windows `LastTaskResult = 0`. The test task and temporary script were cleaned up. This verifies script execution/completion; hearing speech and viewing the notification were not independently asserted by the user. |
| Account sessions | Passive checks returned authenticated for WhatsApp Web, Discord and Instagram. No additional sign-in, Discord/Instagram message or call was performed. |
| Current WhatsApp Web layout | Exact Divyansh chat header resolved successfully. The visible account exposed Video call, with no observed Voice call control. |
| Cloud vision | Artificial image correctly returned **4729** and **red**; no private desktop image was uploaded for this check. |
| Cloud voice and command | Gemini Live invoked `assistant_command` once for `calculate 27 * 13`, received verified **351**, and returned audio with transcript “The answer is 351.” |

Current evidence files are in `scratch/assistant_features.json` and `scratch/reminder_delivery_check.json`. Conversation contents and full private WhatsApp screenshots were not retained in this report. The phone-glyph asset contains only the cropped icon.

## Remaining verification limits

- The real Divyansh call proves the installed app/account can call. It was operated through the computer-use tool; the newly added native JARVIS call handler has synthetic guard/control tests and requires a separately authorized real acceptance call before being considered verified end to end.
- This native WhatsApp build exposed no owned accessibility controls during diagnosis. The visual fallback depends on the observed UI and can stop honestly if the layout changes. Actual incoming-call answer/decline/end through that handler has not been tested with a real incoming call.
- Real Discord/Instagram send and call acceptance remains untested. Implemented controls are covered on synthetic pages, and login is verified.
- A live Windows/phone notification collector is not connected to the aggregator. Phone/SMS access and SMS delivery are not verified. Unimplemented social posts/comments do not claim success.
- Ollama was offline during startup. Hybrid cloud voice/text is available; that does not establish functioning offline speech/reasoning on this laptop.
- Whole-repository legacy tests were not run indiscriminately: some perform real communication, app shutdown or permission changes, and several assert older fake-success contracts. These results are not a claim of full repository coverage or 100% Iron Man functionality.

The earlier automatic approval rejection concerned a WhatsApp window binding whose screenshot showed unrelated ChatGPT content. Fresh window selection and the user's manual restoration resolved that mismatch; no unrelated ChatGPT UI was operated.

## Runtime handoff

The assistant is being handed back running with the latest fixes. Launch uses the installed `python.exe` with `CREATE_NO_WINDOW`, which hides the console without hiding the Qt dashboard. A prior hidden-window launch hid the dashboard; a `pythonw` attempt exited, so neither was used for the final handoff. The successfully running console-free dashboard was independently found as an owned visible Qt window (minimized when inspected). Computer-use restoration reported user input, so repeated window manipulation was avoided. Final process and microphone/cloud checks are recorded below after restart verification.

Final instance: **PID 9268**, exact project `main.py` verified, process running, owned dashboard **visible and not minimized**, Gemini Live connected, default Realtek microphone stream open and playback started. Evidence: `scratch/assistant_handoff_20261001.json`; startup logs: `scratch/assistant_boot_handoff_20261001.stdout.log` and `.stderr.log`. The assistant was left running.

## Voice and typed-chat follow-up improvement

At the user's next request, both input modes were checked again and improved:

- A shared prefix normalizer handles conversational starts such as “Hey Jarvis, please…” without changing the body of a message.
- Recent exact, verified contacts are shared across voice and typed chat. Supported “usko/uske/uski/usse”, “same contact” and “reply…” commands resolve for 120 seconds; failed, unverified, expired or cross-platform targets request clarification. Contact context uses elapsed time, not the adjustable system clock. Ordinary conversation is not treated as a contact action.
- Discord/Instagram named chat opening is now supported and checked against the actual conversation URL. WhatsApp named call instructions use the exact parsed recipient rather than swallowing platform words into its name. No real message or call was placed for this improvement.
- Typed chat and local voice workers return the actual structured result, log it and speak it once. Empty results do not invent completion. Bridge-tagged “Jarvis, stop!” bypasses the action lock, flushes queued speech and clears the UI processing state without speaking another acknowledgement.
- The dashboard timeout now says the final result has not arrived rather than fabricating “Command execution completed.”
- Live instructions preserve message/contact text and defer recent-recipient resolution to the shared command pipeline.

New acceptance coverage is in `tests/test_voice_chat_parity.py`. Actual account communication is mocked; dashboard submission runs the production JavaScript function in isolated Chrome pages. Final regression and runtime evidence for this follow-up are recorded below.

The usage guide is `docs/JARVIS_USE_GUIDE.md`. Current speaker echo protection is retained unless the user selects headphones. This work does not claim a dedicated offline wake-word detector, speaker identity recognition, verified real incoming-call controls or fully working offline inference.

### Final voice/chat results

Later expanded acceptance and the latest handoff are recorded in [JARVIS_ACCEPTANCE_2026-10-01.md](JARVIS_ACCEPTANCE_2026-10-01.md), including a subsequently discovered real Qt chat-bridge fault and its verified fix. The observations below are historical.

The final affected suite, now including `tests/test_voice_chat_parity.py`, passed **185 tests, 2 dependency warnings, in 37.01 seconds**. The same six memory/adaptive/UI suites also passed **124 tests in 19.07 seconds** during this follow-up. This is **309 distinct passing cases**, not a sum of repeated runs. Syntax compilation passed for the six changed implementation/verification files.

Two actual runtime faults were found beyond mocked tests:

- Legacy `send_realtime_input(media=...)` connected but produced no transcript, tool call or response in two 40-second synthetic-speech checks. Dedicated `audio=types.Blob(...)` produced the input transcript “jarvis, calculate 27 * 13.”, exactly one verified calculator call returning 351, and native response audio with “The answer is 351, Boss.” The production microphone sender now uses that same dedicated field. This passed again with the final prompt. Evidence: `scripts/verify_voice_audio_command.py` and `scratch/voice_audio_command_check.json`. The fixture is Windows SAPI-generated, 16 kHz mono PCM; no user speech was recorded for this fixture and no account communication was allowed.
- A startup process exited with native code `0xC0000005`. Faulthandler located a COM interface release during cyclic garbage collection while the voice thread imported HTTP dependencies. The microphone endpoint wrappers are now initialized explicitly with COM and retained by the assistant rather than becoming eligible for that unrelated collection. The corrected process survived startup and the handoff observation. Evidence: `scratch/assistant_startup_fault_20261001.stderr.log`; regression coverage checks COM initialization and retained microphone references.

After audio recognition began working, the laptop's background audio caused unrelated transcriptions and a model-generated reminder command. The final build requires each voice utterance to start with “Jarvis”, “Hey Jarvis” or the supported Hindi spelling. Before that address is recognized, cloud response audio/text, tool execution, fallback dispatch and memory updates are suppressed. The local speech worker applies the same rule. Typed commands remain usable without the prefix. Tests cover background audio before and after an addressed command, split transcript chunks, the empty tool completion, audio suppression and ignored memory. This is a cloud transcript gate, not an offline wake-word detector or proof of speaker identity. A background recording that itself directly addresses Jarvis may still satisfy it. Microphone audio is still sent while unmuted.

Spoken “set a reminder”, “set an alarm” and “create a timer” now select actual reminder controls instead of falling into ordinary conversation because of the article. No new real message, call or reminder was intentionally created for this follow-up.

The production dashboard's command and chat submission functions passed isolated browser checks, and addressed/unaddressed voice workers passed the shared-pipeline tests. A real desktop typed-calculation attempt was interrupted by detected user input and a minimized target window; no calculation was submitted and that manual check is **not verified**. Screenshots initially showed another foreground window despite the JARVIS binding; fresh activation restored the actual dashboard, and no input was sent to the unrelated window.

Latest handoff supersedes the earlier PID 9268 and intermediate PID 30888: **PID 5528**, exact project `main.py`, one running assistant, console hidden, owned dashboard visible but minimized by the handoff observation, cloud connected, Realtek microphone open and playback started. Uptime at the recorded check was 95 seconds, with zero voice tool executions in this addressed-only runtime. Evidence: `scratch/assistant_voice_chat_handoff_20261001.json` and `scratch/assistant_voice_chat_addressed_20261001.stdout.log` / `.stderr.log`. JARVIS was left running. A physical spoken command from the user and headphone interruption still need real-user acceptance; the successful audio fixture does not establish recognition accuracy for every voice or noisy room.
