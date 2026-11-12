# Browser Search Stage 2.2 Test Results

## Final audit update (2026-11-12)

In the 2026-11-12 final audit, the documented test suites were **NOT RUN**: the audit environment had no Windows host with the JARVIS runtime dependencies (`pywin32`, `playwright`, `faster-whisper`, etc.). The audit was a static review of the live files on `main`. No tests were hidden, deleted, or weakened, and no test files were modified. The prior recorded results below remain the saved baseline. The one code fix from this audit (browser_search engine shadowing, commit `f832f76`) is additive and must be validated on a Windows machine with:

```text
pytest -q tests/test_search_preferences_stage22.py tests/test_web_search_stage2.py tests/test_stage3_search_intelligence.py
```

Rollback instructions are in [SEARCH_FINAL_AUDIT_20261112.md](SEARCH_FINAL_AUDIT_20261112.md).

## Executed (recorded baseline)

Focused command:

```text
pytest -q tests/test_search_preferences_stage22.py tests/test_web_search_stage2.py tests/test_stage3_search_intelligence.py
```

Result: **42 passed**. Coverage includes all four browser preference scopes, global/per-browser independence, reset behavior, custom templates, URL encoding and rejection, malformed configuration recovery, provider fallback reporting, natural Hinglish preference commands, custom-engine lifecycle, no-CDP no-launch behavior, existing handler compatibility, configured provider preference, and the 73-tool registry.

Broader relevant regression command:

```text
pytest -q tests/test_search_preferences_stage22.py tests/test_web_search_stage2.py tests/test_stage3_search_intelligence.py tests/test_web_search.py tests/test_web_reliability.py tests/test_live_search_recovery.py tests/test_extended_browser_controls.py tests/test_chrome_whatsapp_web_search.py tests/test_web_automation.py tests/test_web_first_master.py
```

Result: **138 passed, 5 failed, 1 warning**. All 5 failures are outside the changed search functionality and are in two existing files:

- `tests/test_web_automation.py`: 2 failures in WhatsApp tool naming/foreground messaging.
- `tests/test_web_first_master.py`: 3 failures in local app/window verification, YouTube-vs-web search priority, and WhatsApp URL alias resolution.

The saved baseline artifact reports failures in both same files (3 in `test_web_automation.py`, 3 in `test_web_first_master.py`). The current run has no new failure in the new preference, search-provider, search-reliability, or browser-search assertions. Their differing exact per-file counts reflect run conditions; unrelated code was not changed to chase those assertions.

Compilation succeeded for all modified Python modules. No full 71-file baseline suite was rerun in this assignment; the prior Stage 2.1 closure records 999 passed, 40 failed, and 5 timeout-affected files for that run.

## Browser-session test limitation

CDP port 9222 was inactive. The no-CDP test confirms the browser search returns safely without invoking browser automation. Actual existing-session navigation/reuse is therefore **NOT VERIFIED**. No browser was launched for testing.