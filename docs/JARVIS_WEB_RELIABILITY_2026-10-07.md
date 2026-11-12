# Internet answer reliability — 7 October 2026

## Understanding

The existing source-grounding repair searches fresh pages and validates cited passages/numbers. Two remaining gaps affected accuracy: colloquial Hindi/Hinglish and abbreviations could miss English sources, and matching a number/quote did not establish its meaning (ODI versus Test, announcement versus denial). Page extraction also treated an unrelated homepage story timestamp or website creation date as publication evidence.

The Graphify report and the router → shared pipeline → registered web handler → page reader/AI engine → authoritative voice delivery path were reviewed. Existing tools, providers and AI policy are reused; there is no new dependency.

## Plan and implementation

- Expand ordinary India/New Zealand abbreviations and century terminology. Translate colloquial Hindi/Hinglish lookup wording into search terms through the existing AI engine, preserving the exact original question for answering. Reject rewritten queries that introduce or lose numeric values. Do not ask the rewrite step for an answer.
- Validate page relevance using the prepared search query, while checking factual scope against the original question. Explicit historical years can read historical sources rather than being treated as a current-stat question.
- Preserve official cricket-source discovery and dated evidence. If the first answer cannot be verified, make one bounded focused search for better sources. Do not put a guessed answer into the search or loop indefinitely. A supplied public source URL is retained for reading.
- Generate the draft at temperature 0.1, then make a separate history-free verification request at temperature 0.0. Check every claim's meaning, format, team/opponent/year, negation, completeness and conflicts against actual supplied evidence. Reject missing/duplicate/boolean claim IDs, unavailable checks and unsupported results. The check uses the same configured provider, not an independent external authority.
- Propagate the explicit inference temperature through existing local/cloud fallback. Ordinary conversation retains its previous default of 0.7 and the existing Charon voice.
- Distinguish article publication from site/organization creation and unrelated news-list timestamps. Always show retrieval/check time separately, in the laptop's local timezone. An undated stable source no longer receives an invented publication date.
- Preserve private-address/redirect filtering, untrusted-content handling, sensitive-content/cloud policy, confirmations and the checked-answer voice delivery added previously. Research and verification prompts do not enter conversation history.

## Tests

Final affected regression run: **558 passed, 1 warning in 59.05 seconds**. Coverage includes web reliability, source/pixel grounding, voice recovery and continuity, AI fallback, real isolated Qt chat bridge, existing task/check-in behavior, mocked social/desktop actions, and security confirmations. No real contact, power or live desktop-capture action was used in these checks.

Four real public internet probes all returned successful, fact-checked answers:

- `ind vs nz T20 series squad October 2026`: official BCCI announcement and the full squad.
- `Virat Kohli ke ODI mein kitne shatak hain`: dated page evidence for the ODI count.
- `विराट कोहली के ODI में कितने शतक हैं`: translated search terms, original-question scope retained, dated ICC evidence.
- `Search the web for Python programming documentation official source`: official documentation destination; check time displayed without borrowing a homepage story's publication date.

Evidence: `scratch/web_reliability_probe_20261007.json`. The four final probes took approximately 10–21 seconds including search, reading and the second verification request.

Two additional real-provider probes deliberately supplied faulty drafts over synthetic evidence: a Test count presented as ODI, and a denial contradicted by an announcement. Both were rejected by the configured checker, not merely by a mocked decision. Evidence: `scratch/web_fact_check_adversarial_20261007.json`.

## Review

This adds a second context check and bounded recovery; it cannot guarantee that every generated statement is correct. Both inference passes use the configured AI provider, so shared model errors remain possible. Search/translation/provider outages can produce an honest unverified response. Current queries still require sufficiently recent dated evidence (31 days), which may conservatively withhold a valid older or undated source. Explicit historical questions are evaluated in their requested scope.

Keyword relevance is not full semantic search. Query translation can fail or be imperfect; the original question is therefore retained for the final scope check. The extra verification and optional recovery add latency. Local-only and credential-screen policies remain in force.

## Final

The tested version was loaded into the exact JARVIS project as process 13196. Startup reached the ready state, Gemini Live connected and Charon TTS received HTTP 200. Runtime status is recorded separately in `scratch/web_reliability_runtime_check_20261007.json`; passing these tests does not establish recognition of a new spoken command from the user.

After the startup greeting and microphone warmup, the repeated health check passed: current PID, fresh telemetry, connected session, capture enabled, increasing sent frames and zero send errors. The initial sample before warmup was not treated as successful audio-flow verification.
