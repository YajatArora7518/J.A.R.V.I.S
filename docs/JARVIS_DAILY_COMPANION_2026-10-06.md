# Daily companion update — 2026-10-06

The existing task store, emotional context, ambient loop and proactive speech checks now support local daily planning. No extra dependency, camera monitoring or personality mode selector was added.

## User preference

One casual check-in per day, with planning and progress questions at free moments. Morning planning happens at the first suitable session before 18:00. Evening progress review defaults to 21:00 and can be changed through chat or voice. Questions only run while JARVIS is open, during 07:00–23:00, after startup and conversation delays, with 15–300 seconds of desktop inactivity. Activity age is read; keyboard content and screen contents are not captured for these check-ins.

The daily store records goals, actual task IDs, self-reported notes, delivered questions and pauses. Delivery is counted only when the speech callback accepts it; a muted/busy/failed callback rolls back proactive deduplication. The user can defer for an hour or pause for the rest of the day. Meaningful recorded absence prompts a question about what happened; no offline activity is invented.

## Conversation and classes

Shared voice/chat instructions use ordinary Hinglish and adapt between playful friend, caring sibling and a patient teacher. Occasional light teasing is consented, but stress, distress and stop requests call for listening rather than roasting. Corrections require reasons. Study replies ask a useful question about the user's attempt and include an explanation; quick answers do not require a quiz.

Only explicitly saved timetable rows enable class check-ins. Invalid or overlapping rows cannot partially overwrite the schedule. Existing college assignments are retained. Class questions ask about attendance instead of asserting absence. The user's actual timetable is still pending; the old demo schedule is not confirmed.

## Verification

Final regression result: **348 passed, 2 warnings**. Executed `tests/test_daily_companion.py`, `test_reference_upgrade.py`, `test_voice_chat_parity.py`, `test_assistant_repair.py`, `test_natural_reply_voice.py`, `test_dashboard_acceptance.py`, `test_assistant_controls.py`, `test_extended_assistant_controls.py`, `test_social_chat_browser.py`, `test_whatsapp_production_upgrade.py`, `test_security_confirmation.py`, `test_holographic_ui_replacement.py`, and `scripts/test_proactive_assistant.py` through pytest. The focused planner/voice run passed **110 tests** before the full run.

Isolated fake-clock acceptance covers persistent goals, exact completion, progress without false completion, busy/quiet/away suppression, one casual question per day across restarts, pauses, actual absence, valid/invalid timetable rows, preserving college data, class question context, corrupt store preservation and shared voice/chat state. Mocked Live packets cover recording an already answered voice turn once and leaving unanswered turns to the command pipeline.

The actual unshown Qt dashboard/WebChannel verified two arithmetic inputs and one temporary daily plan: exactly one pipeline call, user bubble, answer bubble and action entry each. Three speech requests were recorded rather than played. The temporary plan survived a fresh planner load. Report: `scratch/dashboard_bridge_check.json`. The test never edits the user's real goals.

Rendered dashboard checks passed at 1440×900 and 1100×700 with no page errors or out-of-bounds controls. These checks verify local behavior and prompt integration; they do not establish that every generated conversational reply feels human, or that every real microphone utterance succeeds.

The exact previously running project process was verified and replaced with the updated app (PID 5444). Runtime health confirms mic capture enabled, an active voice session and audio frames sent without send errors; `scratch/daily_companion_runtime_check.json` records the snapshot. No real user utterance was tested during this update. The startup Charon greeting request timed out and used the existing Windows speech fallback, so natural speech availability remains dependent on the provider.

## Boundaries

Saved goals and notes are context, not authorization to run their text as laptop commands. Ordinary app and social commands keep their existing shared pipeline and verification. No outgoing messages, calls, shutdown or restart were used to test this update. Charon speech retains the user's existing approved configuration. Check-in follow-ups accept one voice utterance for 30 seconds after speech ends; direct voice commands otherwise retain the Jarvis address gate.
