# JARVIS optimization and bug repair — 2026-10-07

## Understanding

The request was to find and repair glitches in the existing standalone assistant, preserving working features. The existing Graphify report and actual callers were inspected: typed/Live commands share the pipeline; document analysis supplies YouTube recommendations; contact import and WhatsApp resolution share the local directory; search uses HTTP providers with a controlled-browser fallback. The September graph was stale, so the installed local Graphify AST update was attempted after changes; its result is recorded below.

Concrete problems were reproduced with isolated regression tests before their patches:

- Invalid/headerless or unrelated empty CSVs could erase previously imported contacts. Nameless valid phone contacts were incorrectly rejected.
- Browser export committed its rows before checking the full-contact count and then saved metadata separately. A partial export could therefore replace valid data.
- A failed CSV selection retained the old selected file. Uploading CSV also retained the old PDF context.
- OAuth/network sync held the directory lock for the entire operation, blocking ordinary contact lookup.
- Different display punctuation for the same phone produced false duplicate-person ambiguity across sources.
- Follow-up document answers overwrote the whole-document topic inventory, narrowing later plans/resources to one earlier question.
- Trailing whitespace alone marked a fully read document as partial. Extraction read all allowed pages/slides before applying the character bound; text uploads read the whole file.
- Changing a file during extraction could cache inconsistent content. AI provider exceptions discarded successfully extracted text instead of using the honest extraction fallback.
- Hindi spoken video commands and document follow-ups did not consistently reach their shared tools. Malformed video URLs could raise during intent handling.
- Browser initialization failures left an unusable event loop and unawaited request. Concurrent starts were not serialized.
- Early irrelevant browser-search cards consumed the result budget before filtering, hiding useful later results.
- Search cache grew without a size bound, retained expired unique queries, returned mutable shared results and had unsynchronized accesses.
- A repeated cached Live tool result set Working and returned without restoring the ready/speaking state.

## Plan

Repair shared helpers and boundaries; retain existing readers, providers, browser engine, voice and action verification. Keep account/desktop effects isolated in tests. Validate affected behavior, broaden regression once, check syntax/whitespace, then launch the updated app and inspect fresh audio telemetry.

## Implementation

- Contacts CSV validates recognized headers, row shape, row limits and the full-export count before writing. Rows and completeness/method metadata commit together through the existing atomic save. Phone-only contacts are retained. Failed new selection clears the previous CSV.
- Google export uses that validated commit rather than import-then-mark-complete. Contact locks now cover local state/save only, allowing directory lookup during slow network/OAuth operations.
- Phone identity strips display whitespace, parentheses, dots and hyphens, preserving actual numbers/country codes; distinct identities still require clarification.
- New uploads clear stale document context. Specific follow-up answers no longer replace the cached whole-document overview.
- PDF/PPTX extraction stops when the 60,000-character preview fills; text reads at most 60,001 characters. Page/slide and byte limits remain. Whitespace does not create false partial status. File stamps are checked before and after extraction.
- AI provider/checker failures return extraction-only headings with `analysis_verified=false`, preserving readable content without invented explanations.
- Added Hindi Thermo/KTG and video-action parsing plus Hindi attachment follow-ups. Video URL parsing returns rejection instead of raising for malformed/nonstandard endpoints.
- Browser startup is serialized, signals initialization failure promptly and closes an unsubmitted coroutine. Existing timeout cancellation remains.
- Browser search counts relevant results, continuing past unrelated early headings within the existing scan limit.
- Search cache is locked, uses monotonic expiry, prunes expired entries, retains at most 128 queries and copies result data at insertion/retrieval. Fresh/time-sensitive queries still bypass it.
- Cached Live replies restore the appropriate ready/speaking/busy state while preserving no-repeat execution.

No new dependencies, provider/model/Charon changes, message sends, calls, power actions or continuous camera observations were introduced.

## Tests

New `tests/test_optimization_repairs.py` contains **30 regression cases**, covering the behaviors above. They use temporary synthetic documents/contacts, mocked providers/recipients, synthetic browser controls and local async loops; no real account writes occur.

Initial focused reproductions: 13 failed/2 passed; after the first repairs, 62 affected checks passed. Four further defects reproduced in the next focused run and four in a later run; their patches were verified. Subsequent affected runs: **111 passed**, then **205 passed**.

Final broad affected regression: **682 passed, 1 warning, 44.81 seconds**. It includes document/media/contacts, browser/source/search reliability, voice/chat continuity, UI state, camera/banter, WhatsApp/social mocks and synthetic pages, confirmations, memory, companion and proactive behavior.

Optimization evidence: the synthetic 30-page PDF preview test extracts **5 pages instead of all 30**, still respects the character ceiling and marks omitted content partial. The cache test submits 300 distinct queries and verifies the 128-entry bound and mutation isolation. These are bounded-work checks, not a measured universal speedup claim.

Changed modules compiled successfully. Scoped Git whitespace check passed; only an ordinary LF/CRLF notice appeared. No broader tests were repeatedly run after their final pass.

## Review

Whole-account Google export/login and actual JARVIS Chrome lecture playback remain account/browser acceptance checks, not covered by mocked tests. The prior in-app public playback test is not relabelled as a JARVIS Chrome test. Scanned/image-only documents and legacy PPT retain their existing honest limitations. Network availability, captions, ads and changing page layouts remain external dependencies. These repairs do not promise a bug-free assistant or unrestricted administrator access.

## Final

Updated app launch and fresh runtime health are recorded below. Only the exact project entry point is targeted for restart; unrelated Python processes and browsers are preserved.

Local Graphify update completed successfully with `--no-cluster`: **4,937 nodes / 12,213 edges**, 151 uncached files extracted. The tool backed up the curated graph before replacing `graph.json`. No LLM clustering or semantic-extraction API was used.

Runtime verification: no old exact-project process was running, so the updated GUI was launched as **PID 34500**. Host inspection returned **Responding=True**. Telemetry matched the new PID and was **2.31 seconds old** at the recorded probe, with Live connected, mic enabled/unmuted, **zero send errors / zero reconnects**. Separate fresh readings showed sent audio frames advancing **645 → 1,195** and captured frames **704 → 1,254**. The two closely spaced samples inside the saved probe landed in the same telemetry publication interval; the later separate sample confirms progression. Startup log reported runtime ready, connection on attempt one and microphone stream open.

Evidence: `scratch/optimization_runtime_probe_20261007.json`, `scratch/optimization_20261007.stdout.log`, `scratch/optimization_20261007.stderr.log`. No microphone speech acceptance claim is inferred from transport telemetry alone.
