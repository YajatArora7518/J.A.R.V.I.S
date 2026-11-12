# Conversation and laptop task upgrade — 6 October 2026

## Understanding and plan

The existing project already provides local goals/check-ins, verified app launching, native/browser social controls, screen inspection, memory, adaptive persona and a security-aware planner. The missing behavior was a sustained voice session, consistent spoken tool replies, clear sequences reaching the shared pipeline, and direct memory inspection/deletion. These changes extend the existing paths without new dependencies or removing confirmations.

## Implementation

Start speaking with `Jarvis` once, or press **Talk to Jarvis** once. Subsequent turns are addressed until an explicit `ab wait kar`, `baad mein baat karte hain`, `pause conversation` or `stop listening`. No fifteen-second deadline ends the conversation. Pausing returns to wake-word/button behavior; it does not shut down the mic or app. `ruk`/`ruko`/`stop` stops speech while preserving the conversation. A muted microphone still needs enabling. Reconnecting preserves session intent. Health snapshots expose `conversation_active` without saving audio/transcript content.

General Live conversation retains the configured Charon voice. Exact typed/pipeline replies now use reply-only Gemini TTS with the same Charon voice and relaxed Indian Hinglish style. The request contains the reply plus constant voice/style metadata; no extra memory, screen, files or tools. Fully completed short replies retain the bounded process-only cache. Stop cancels the async request/playback. Unavailable natural speech shows a notice and leaves the reply in chat rather than silently changing to Windows voice. Provider generation can still take seconds or fail.

A verified exact `Opened Discord.` tool result is presented as `Discord khol diya, bhai.` This is presentation only; failed/unverified results and message bodies are untouched. Recent typed and native voice replies share the existing redacted, bounded dialogue history. Newly built/reconnected Live sessions receive recent dialogue as data, not authorization; execution targets/contacts continue to use the existing verified context. An already-open Live socket does not instantly ingest arbitrary new typed conversations.

Explicit sequences use `then`, `phir`, `aur`, `and` or semicolons between recognizable commands, with up to eight steps. All steps use the existing command pipeline, authorizations and verification. Progress appears in recent actions. Failed, unverified or confirmation-requiring results stop subsequent steps and list what has not run. There is no automatic retry of an uncertain communication, and no automatic continuation after confirmation; provide the remaining commands after resolving the blocker. Ordinary prose and lists of app names keep their existing handling. In a sequence, outgoing message text must be quoted to distinguish it from following commands; separators inside quotes remain literal data.

Examples:

- `open Discord then calculate 13 * 17`
- `WhatsApp par ExactContact ko message bhejo "Main 10 minute mein aa raha hoon" then open Discord`
- `memory dikhao`
- `yaad rakh: study subject: C programming`
- `memory mein study`
- `bhool ja: study subject`

Memory commands inspect the actual existing store, verify save/delete persistence, and require one exact unique key for deletion. No broad fuzzy deletion is performed. Inspection/deletion utterances do not become new extracted personal facts. Existing naturally adaptive Hinglish banter, corrections, teacher-style questions, on-request screen help, app recovery and daily companion behavior are retained. No timetable was added, no extra check-ins scheduled, and no invented personality modes.

## Verification and review

Final affected suite: **429 passed, 2 warnings in 48.87 seconds** across seventeen files, including voice/chat, daily companion, adaptive context, memory, social controls, security, speech and dashboard regression tests. Historical memory tests now exercise the actual local-first/policy-gated implementation. The WhatsApp sequence fixture mocks the registry throughout; real outgoing communications and OS power actions were not performed.

The tested production app was restarted as PID 27028. Its startup Charon TTS request returned HTTP 200 and used actual audio playback, rather than the old Windows voice fallback. Current process/mic/connection and Qt evidence are captured in `scratch/conversation_upgrade_runtime_check.json`. Physical multi-turn mic acceptance is not interchangeable with the synthetic three-turn test.

Real reply-only Charon TTS generated the test sentence in **6.63 seconds**, producing **103,680 bytes** of audio. Saved evidence: `scratch/natural_hinglish_probe.json` and `.wav`. Audio capture was isolated from sound devices for this provider probe; accent/subjective quality still needs the user's judgment. The mock tests cover provider payload isolation, cache reuse, sequence stop/no retry, quoted text integrity, memory persistence and three voice conversation turns with one initial wake.

Actual production Qt/WebChannel acceptance verifies typed arithmetic, a two-step arithmetic sequence, one user/answer bubble per submission, continuous Talk activation, explicit pause, a voice user bubble and isolated planner persistence. No real contact was messaged/called or Windows power action performed.

The microphone echo guard still pauses capture while playing through laptop speakers. Voice interruption during speaker playback is therefore not guaranteed; the chat stop control works independently. Headphone barge-in configuration remains available. While a conversation is active, there is no speaker identity authentication: nearby speech can be treated as a turn. Pause or mute when finished. Login, OS permissions, unsupported tasks and provider availability remain real dependencies; the assistant cannot truthfully claim unrestricted universal laptop control.

Official TTS API schema: https://ai.google.dev/gemini-api/docs/speech-generation
