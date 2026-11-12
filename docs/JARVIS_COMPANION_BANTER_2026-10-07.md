# Respectful companion and saved banter — 7 October 2026

## Understanding

The shared style previously allowed only light teasing and explicitly prohibited named modes. The user now explicitly requested a saved unfiltered banter preference, while also asking for respect, logical disagreement and accurate internet answers. Local/cloud text generation, Live instructions and drafting all consume this style. The generated Graphify report was consulted to trace the shared command pipeline, AI engine and Live entry point before these changes; the existing graph is historical, not a regenerated graph of this patch.

Camera observations must not infer emotions, mood or mental state from appearance. The alternative implemented is a neutral check-in and adaptation to the user's own words. Background camera awareness remains disabled.

## Plan

Reuse the shared style and command pipeline. Save a small non-secret banter preference, make exact voice/chat controls persist, prevent old Live instructions from restoring disabled banter, and preserve all action confirmations and source verification. Use the existing daily check-in rather than creating another scheduler or camera monitor.

## Implementation

- `core/conversation_style.py`: one shared dynamic style; consented rough Hinglish banter with respect, reasoned corrections, gentle response to distress, and no empty promises. `config/conversation.json` starts with the user's requested unfiltered banter enabled.
- Exact controls include `unfiltered mode on`, `gaali band karo`, `mujhe gaali mat de`, `गाली मत दो` and `unfiltered mode off`. Writes are atomic and locked; corrupt settings are preserved, with an honest failure result. Quoted messages, drafts and ambiguous mixed requests cannot toggle the setting.
- `core/command_pipeline.py`, `core/ai_multitier_engine.py`, `main.py`: voice/chat use the saved style. If an existing Live session has older instructions, its replies go through the current shared pipeline. A tool reply from that stale session is authoritative, preventing the old model tone from rewriting it. Session resumption retains the old style marker until fresh instructions actually apply.
- Formal drafts use recipient-appropriate wording and finished text without companion banter, invented time windows or stock filler.
- `agent/emotional_context.py`: user-reported “mood off” is recognized. `agent/daily_planner.py`: existing once-daily casual check-in can ask neutral haal-chaal, within existing quiet/busy/idle gates.
- `actions/screen_processor.py`: explicit camera mood requests ask a neutral question without capturing/uploading a frame. Normal camera observations instruct the model to report visible objects/actions only; detected emotional claims are rejected. English/Hinglish/Hindi camera intent routing now chooses the camera, including `cam` and `कैमरा`.
- `core/prompt.txt`: saved tone controls and actual-page internet evidence are explicit. Research keeps its checked meaning, citations, dates and uncertainty. Tone does not change search queries, message payloads or permissions.

## Tests

All tests use isolated preference files; camera frames and outgoing communication/power actions are mocked.

1. Initial focused suite: **132 passed**, one warning, 7.93 seconds.
2. Broad affected regression suite: **583 passed**, one warning, 69.85 seconds.
3. After adding natural stop-command variants and refining draft wording: **586 passed**, one warning, 70.04 seconds. Files: `test_companion_banter`, `test_web_reliability`, `test_source_grounding`, `test_live_search_recovery`, `test_session_continuity`, `test_conversation_upgrade`, `test_runtime_glitches`, `test_daily_companion`, `test_reference_upgrade`, `test_voice_chat_parity`, `test_assistant_repair`, `test_natural_reply_voice`, `test_dashboard_acceptance`, `test_assistant_controls`, `test_extended_assistant_controls`, `test_social_chat_browser`, `test_whatsapp_production_upgrade`, `test_security_confirmation`, `test_holographic_ui_replacement`, `test_memory_fallback`, `test_contextual_adaptive`, `test_web_search`, `test_chrome_whatsapp_web_search`, and `scripts/test_proactive_assistant.py`.
4. Final stale Live reply guard: **154 passed**, one warning, 7.82 seconds across companion banter, session continuity, runtime glitches, Live search recovery and source grounding. This was the final code change; the complete broad suite was not repeated after this narrow guard.
5. Real configured text provider: corrected `2^10 = 100` to 1024; used friendly Hinglish banter on request; dropped roasting for self-reported distress. Final follow-up draft contained a short polite email with no gaali, invented date or “I hope this email finds you well” filler. Synthetic prompts only; no microphone/camera input or messages sent by the probes.
6. Real public live search: Hinglish ODI-century question returned **55**, using the ICC article dated **30 September 2026**; both evidence and semantic fact checks passed. Completed in 21.74 seconds. [ICC supporting article](https://www.icc-cricket.com/media-releases/kohli-closes-in-on-gill-at-top-of-icc-men-s-odi-batting-rankings).
7. Updated app started as PID **26064**, exact absolute project `main.py`, responsive window, Live connection established, microphone capture enabled and no send errors. Health samples saved separately. Charon remains configured for both Live and typed reply speech; background camera remains off.
8. Targeted whitespace review passed; no new dependency or credential changes.

Evidence: `scratch/probe_companion_banter_20261007.json`, `.followup.json`, `scratch/companion_banter_runtime_check_20261007.json`, and the corresponding JARVIS startup logs.

## Review

Unfiltered is a tone preference, not a safety/authentication bypass. Consent to banter does not permit outgoing actions without a current resolved request or disruptive operations without confirmation. Model wording remains probabilistic: the real probes demonstrate examples, not a guarantee about every future answer. Internet answers still depend on available source evidence and providers; insufficient evidence produces an honest unverified response. Camera mental-state inference is not implemented, and the keyword guard is defense in depth rather than a universal semantic classifier. Speech transport was checked, but this turn did not physically speak into the user's microphone or verify what they heard.

## Final

Saved respectful rough banter is enabled, natural stop controls work across voice/chat, logical correction and gentle listening instructions are shared, camera check-ins avoid emotion inference, and the existing internet verification pipeline remains active.
