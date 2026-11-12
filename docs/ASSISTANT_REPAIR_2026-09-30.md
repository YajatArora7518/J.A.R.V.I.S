# JARVIS assistant repair — 30 September 2026

## UNDERSTANDING

The working tree already contained many earlier, uncommitted changes. Those changes were preserved. The Graphify report dated 27 September was consulted, then the actual voice → command pipeline → tool registry → executor paths were traced in source.

Cloud AI was disabled by default. The legacy OpenRouter fallback called a nonexistent Ollama `generate` method and returned the same offline message instead of executing useful work. Local transcription and command execution blocked the audio loop, and the microphone could feed JARVIS's speech back into the assistant. Reminders were classified but never registered as an executable tool. Known services lost their browser fallback. Discord send/read handlers returned hardcoded success and sample messages. Tool invocation could replay an action after a handler raised `TypeError` or `AttributeError`.

## PLAN

Reuse the existing laptop tools, restore configured cloud voice and reasoning, keep explicit local-only overrides, route voice and chat through the same pipeline, stop acoustic feedback and duplicate executions, register real reminders, and replace social messaging placeholders with bounded browser actions.

## IMPLEMENTATION

- `config/runtime.json` selects hybrid AI, Gemini 3.5 Flash-Lite text and Gemini 3.8 Live voice. Existing API credentials stay in their existing secret configuration. `JARVIS_CLOUD_AI=false` still overrides hybrid settings.
- Voice actions call one `assistant_command` tool. The command pipeline selects real tools, applies existing authorization and returns the actual result. Commands are serialized; repeated identical tool calls within one Live turn reuse the first result.
- Text and voice failures are spoken. Local transcription/inference runs off the audio event loop. Repeated speech and local utterance buffering are bounded. Speaker-safe defaults pause mic capture during speech and for 500 ms afterward. With headphones, `voice_barge_in=true` enables Gemini voice interruption; typed `stop` remains available in either mode.
- Missing cloud voice connections switch to local speech after bounded reconnect attempts; missing local recognition leaves typed commands usable. Fallback errors are reported honestly rather than repeatedly acknowledged as successful actions.
- Screen and camera background permissions are disabled. Explicit screen requests capture and analyze the image through the configured model. Failed visual inference is reported as a failure. Screens whose title/query indicates credentials are blocked from cloud analysis. This heuristic is not a comprehensive sensitive-content detector.
- Natural reminder times are parsed locally, including `10 minute baad`, `tomorrow at 9:30 pm` and relative timers. Ambiguous `9 baje` asks for morning/evening. Windows Task Scheduler uses unique job names, escaped XML and quoted Python message literals; reminder notification scripts also speak via SAPI.
- Installed apps open without a repeated desktop-versus-web question. Known web services have exact browser fallbacks; unknown apps still fail honestly. Opening a new browser service preserves existing tabs.
- Explicit Discord/Instagram commands take priority over generic WhatsApp verbs. Browser actions require login, an exact unique recipient, an empty message draft and observable message insertion. A send is never automatically repeated when verification is uncertain. Visible reads return actual page text. Call buttons report a request unless connection state is confirmed. Sample Discord messages and fake production contacts were removed.
- Proactive speech is connected to the existing ambient engine and suppressed while JARVIS is speaking or executing a command. Existing Windows authorization boundaries remain intact.
- Live's empty intermediate tool completion preserves the execution ledger until the spoken answer completes. Message capitalization is preserved in parsing and deduplication.
- Native WhatsApp targets the actual `WhatsApp.Root.exe` window. An existing app-owned WebView connection is optional; otherwise Windows offline OCR verifies the exact chat, empty draft, typed message and submission. Uncertain sends are protected against immediate retries. No debug registry configuration was added.
- Background account checks examine existing tabs without launching, navigating or focusing them. Explicit service opens reuse redirected tabs and match real hostnames. Signed-in Instagram inbox URLs with a `__coig_login` query are correctly recognized.
- Discord mute/deafen checks the actual button state and disconnect uses the named Disconnect control. Generic phone calls validate phone numbers, avoid shell interpolation and report an intent request without claiming a connection.
- Proactive assignment reminders use real deadlines within the next 24 hours. Undated, overdue and distant tasks are not falsely announced as due soon.

## TESTS

Final command: `python -m pytest tests/test_assistant_repair.py tests/test_assistant_controls.py tests/test_social_chat_browser.py tests/test_security_confirmation.py -q --disable-warnings -p no:cacheprovider` — **85 passed**, one dependency warning, 24.91 seconds.

The browser regression runs installed Chrome headlessly in an isolated temporary profile against intercepted synthetic pages. It verifies actual DOM typing, Unicode/emoji messages, one send, visible message extraction, draft preservation, unresolved recipient protection, named call/answer/end controls and idempotent Discord voice controls. These tests use synthetic accounts and calls. The regression also covers intermediate Live completions, passive background checks, actual verification propagation and phone-call input validation.

Real checks:

- Gemini text returned a response in approximately 1.5 seconds.
- Gemini 3.8 Live returned actual audio.
- A uniquely named future Windows reminder was registered, queried successfully and removed before it fired.
- WhatsApp Desktop and Discord Desktop opened successfully and their running window/process state was checked. Instagram opened at its known URL in the existing Yajat Chrome profile.
- JARVIS dashboard started, the realme Buds T200 input stream opened, cloud voice connected and the process remained responsive. Startup logs are in `scratch/assistant_boot_20260930.*.log`.
- Modified Python files were checked for syntax errors.
- On the user's explicit instruction, **“match dekh le”** was sent once to **Divyansh on WhatsApp Desktop**, using the computer-use skill. The outgoing bubble and double-tick delivery indication were observed. It was not sent again through the repaired pipeline.
- The repaired command pipeline successfully read the visible Divyansh WhatsApp chat. Conversation text was omitted from verification output and artifacts. A failed check while Windows was PIN-locked was repeated successfully after unlocking.
- After the user completed sign-in, both Discord and Instagram signed-in controls were verified in JARVIS's controlled Chrome session. No real Discord/Instagram messages or calls were sent.
- Actual Gemini vision recognized the number 4729 and a red square in an artificial test image. No private desktop image was uploaded for this test.
- Actual Gemini Live called `assistant_command`, the real command pipeline calculated 27 × 13 = 351, and native model audio plus the spoken answer transcript were received. The action executed once.
- The repaired assistant was restarted as process 24728. The dashboard was responsive, Gemini Live connected, the current default Realtek microphone opened, and audio playback started. Logs: `scratch/assistant_boot_verified_20260930.*.log`.
- Syntax compilation passed for 32 modified/new Python files. Whole-tree whitespace checks also found pre-existing formatting issues in unrelated edits; those user edits were preserved.

An earlier exploratory run of older app/addressing/single-execution tests had 20 passing and six failing assertions, including outdated return-type/launcher contracts. That older suite was not re-run wholesale because it performs real desktop and call actions. The final suite is isolated from real communications and validates the repaired paths directly. Do not interpret this work as a passing result for the entire repository test collection.

## REVIEW

The user completed Discord/Instagram login in the controlled JARVIS Chrome session. `connect_social_apps.bat` can reopen that session later. The existing ordinary Chrome login is not automatically transferred to this separate profile. Browser UI selectors can change; unavailable or ambiguous controls produce a failure rather than guessed clicks. Real Discord/Instagram sends, calls and incoming-call handling still need a recipient-specific live acceptance check. Synthetic call controls passed, but they do not prove real account calling works.

The installed WhatsApp version has icon-only call buttons that offline OCR cannot reliably identify. Native WhatsApp voice/video call placement and incoming-call acceptance therefore remain limited; unavailable controls return an explicit failure, never guessed clicks or fabricated success. This work does **not** establish 100% hands-free calling across all three platforms. Phone Link/ADB calls require a separately connected phone and exact phone number. Windows must be unlocked for foreground app actions. Ollama was unavailable during real checks; the configured cloud path was verified and local fallback behavior was tested with isolated substitutes.

The Windows reminder requires the user to be signed in when it fires; waking a sleeping laptop depends on Windows power settings. A powered-off laptop cannot deliver a reminder.

## FINAL

JARVIS is running with cloud voice, local laptop actions and repaired routing. All 85 isolated regressions passed. The authorized WhatsApp message was delivered, native WhatsApp visible reading passed, social account login passed, and real vision/audio/reminder registration checks passed. Native icon-only call controls and real social call acceptance remain unverified or limited as described above.
