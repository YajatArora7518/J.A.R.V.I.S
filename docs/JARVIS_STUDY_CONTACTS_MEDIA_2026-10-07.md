# JARVIS contacts, study attachments and verified video search

## Understanding

The user wants features in the standalone JARVIS project, rather than relying on Codex/ChatGPT connectors. Their WhatsApp contact is **Mumma**. Their example search is Thermodynamics and Kinetic Theory of Gases, preferably Hindi/Hinglish. Work should visibly show **Working**.

The existing YouTube handler opened the first scraped ID and reported playing without checking media state. The shared router treated YouTube queries like opening a site or generic search. Attach sent a filename marker without reading the document. Important-contact updates discarded aliases. The saved Mom alias contradicted the user's actual Mumma contact.

The existing Graphify report was consulted to trace UI → shared pipeline → intent router → tools/browser engine. This is the existing September 27 report, not a newly generated graph. Existing browser, shared AI, security, voice and conversation components were reused.

## Plan

Preserve the existing voice/chat execution lane and account/security checks. Correct names and contact persistence; implement JARVIS-owned imports/sync. Navigate actual YouTube results and validate the requested media. Read real document content, retain one shared attachment context, and ground explanations/resources in source passages. Show Working for command execution. Test affected routes, failure cases and existing functionality.

## Implementation

- **Contacts:** Mom/Mummy/Maa aliases now resolve to **Mumma**. Local directory retains source identity, update timestamps and completeness. Exact duplicate people require clarification, including after alias resolution. Directory phone/email values are not printed or added to AI prompts. Imported contacts are not automatically made important-message alerts.
- **Google integration in JARVIS:** `sync Google contacts` / `mere contacts Gmail se sync kar` use normal Google Contacts export in JARVIS's controlled browser when no app OAuth client is configured. Login is performed by the user. Export must identify the all-contacts scope; partial counts do not become a full-sync claim. Downloaded CSV is imported locally and that exact temporary export copy is removed. `Attach` a Google CSV followed by `import contacts` also works. An optional Desktop OAuth client supports the readonly People API with PKCE, state validation, loopback callback, pagination and Windows account-bound token encryption. No Codex connector credentials are imported into the app.
- **Initial directory:** One verified Mumma contact was seeded from the connected account. This is explicitly marked **partial**; the user's entire Gmail address book has not been verified/imported yet. The app's runtime does not require that connector.
- **YouTube:** Search requests navigate the actual results page even when reusing an existing tab. Results include actual title/channel/direct watch link; Shorts and irrelevant cards are excluded. Hindi/Hinglish is the default, with explicit language overrides respected. Homepage-only commands remain homepage commands. Message payloads remain communication data.
- **Playback:** Opens the selected watch URL, checks correct video ID and advancing media time, and distinguishes ads/paused players from the requested lecture. Can use the visible offered Skip Ad control. A timeout cancels queued browser work so it cannot navigate later after reporting failure.
- **Recommendations:** Compare up to two candidates using bounded caption samples across long lectures. Shared AI selects actual topic passages and a separate history-free check rejects unsupported explanations. Results state their evidence and limits; there is no universal-best, whole-lecture-watched, guaranteed-mark or complete-syllabus claim.
- **Live public search fallback:** Observed HTTP/DDGS unavailability led to a bounded Google search fallback in JARVIS's own browser. It reads actual result headings/links; opaque tracking links are followed normally in temporary tabs to identify final source URLs. CAPTCHA is not solved/bypassed. Existing source-page/date/claim verification remains responsible for factual answers, so result discovery alone does not certify an answer.
- **Attachments:** PDF, PPTX and text are read from the selected real path. PPTX includes tables, grouped shapes and speaker notes. PDF pages/slides accompany topic evidence. Explanations must reference an exact document quote and pass a separate consistency check. Failed extraction/analysis returns an honest extraction-only result. Legacy PPT requests conversion; scanned textless PDF requests OCR instead of inventing topics.
- **Context:** Voice/chat share the current document; failed new uploads clear old context, changed files require reattachment. Plan/resource follow-ups reuse verified topics and cannot be mistaken for new daily goals. File paths and document instructions never enter the multi-action executor. Vague screen follow-ups without an attached document retain existing behavior.
- **Resources/plans:** Search only short academic topic headings, read actual candidate pages/captions, reject readable but unrelated sources, and return links with matched concept evidence. Suggested study durations are estimates; deadline/time questions remain user inputs, not fabricated timetable facts.
- **Working:** Both chat execution and Live tool execution expose Working through the existing THINKING state. The HUD labels show WORKING; normal listening/speaking state returns after success or failure. Charon and existing mic controls remain configured.

## Tests

New tests cover contact import/pagination/preservation/duplicates, browser login and incomplete export, YouTube intent/homepage separation, payload preservation, strict video URLs, media/ad verification, new caption API compatibility, real synthetic PDF/PPTX extraction, attachment injection/change/failure, grounded claims, cached plans, daily-planner separation, resource relevance, Working lifecycle, browser timeout cancellation and search/CAPTCHA failure handling.

Unit tests isolate new browser fallback rather than launching the user's browser when a mocked HTTP provider fails. Legacy Mumma tests now assert the user's requested contact name, and their send/call boundaries are mocked. The old general-search unit test used a real external service; after an observed DDGS failure, provider availability was separated from deterministic execution/redaction assertions. A distinct failure test requires an honest empty result.

Focused runs: 185 passed; then 178 passed after routing changes; then 131 passed for the latest new/web/source checks. **Final affected suite: 652 passed, 1 warning, 38.32 seconds.** Syntax compilation passed. The scoped Git whitespace check passed (only normal LF/CRLF notices). Startup health is recorded below after execution.

Actual probes, using synthetic/public inputs only:

- Real installed PowerPoint reader + shared AI: a two-slide Thermodynamics/KTG fixture returned two supported topics and a verified suggested plan. Evidence: `scratch/study_media_probe_20261007.json`.
- Real public captions: retrieved 368,677 characters for the JEE Wallah lecture; comparison sampled captions from two actual videos and retained four and two supported concept passages respectively. Evidence: `scratch/video_review_probe_20261007.json`. Whole lectures were not watched, and the user's syllabus was not provided.
- Public browser search → actual JEE Wallah watch page → ad observed → lecture time advanced from 0:02 to 5:04; then the test video was paused. This was the available Codex in-app test browser, **not an end-to-end playback verification of JARVIS's Chrome profile**. Screenshot: `scratch/thermo_ktg_video_verified_20261007.png`.
- A public Google browser search returned actual results after the HTTP search provider failed. Chrome was unavailable through the model's computer-use adapter, so the new project CDP fallback was verified with isolated tests, not claimed as a real account/browser acceptance run.
- No new real outgoing message/call, power action, account write, persistent camera observation or timetable change was performed.

## Review

Installed `python-pptx` and `pdfplumber`, and listed them in requirements. Their absence was confirmed before installation. No new credential is hardcoded; personal directory/token files match the existing `*.user.json` ignore rule.

Limits: analysis is bounded to 25 MB, 100 pages/slides and 60,000 characters and marks partial extraction. Scans, embedded images/equations without readable text and legacy PPT are not silently analyzed. AI passage checks reduce errors but do not guarantee correctness. Captions can be imperfect and video quality depends on the user's level/syllabus. Browser page layouts, login, ads, network failures and CAPTCHA can require user intervention. Full Google contact export/login has not yet been verified against the user's JARVIS browser account. No claim of full Gmail sync is made.

## Final

The features are implemented inside the standalone project and share voice/chat routing. Final regression results, restarted process and fresh voice health are added below.

Startup verification: authorized GUI restart launched the exact project `main.py` as PID **9672**. Host process inspection confirmed **Responding=True**. Fresh telemetry matched that PID, with `session_connected=true`, mic enabled and unmuted. Across two samples, captured frames advanced **2746 → 2982** and sent frames **2676 → 2912**, with **zero send errors and zero reconnects**. Startup logs confirmed the dashboard loaded, 72 tools registered and Gemini Live connected on its first attempt. This verifies startup/audio transport; it does not replace the user's spoken-command acceptance test or verify full Google contact export/JARVIS Chrome playback.
