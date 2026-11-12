# Stage 3 Test Results

Focused Stage 2.2 + Stage 3 checks:

```text
pytest -q tests/test_search_preferences_stage22.py tests/test_web_search_stage2.py tests/test_stage3_search_intelligence.py
```

Result: **42 passed**. The suite checks source prioritization, duplicate removal, provider health circuit behavior, bounded retry configuration, table/ranking extraction, distinct publication/update/event/retrieval metadata, sports/esports intent phrases, configured provider preference, search interface compatibility, and tool registry preservation.

Relevant combined regressions:

```text
pytest -q tests/test_search_preferences_stage22.py tests/test_web_search_stage2.py tests/test_stage3_search_intelligence.py tests/test_web_search.py tests/test_web_reliability.py tests/test_live_search_recovery.py tests/test_extended_browser_controls.py tests/test_chrome_whatsapp_web_search.py tests/test_web_automation.py tests/test_web_first_master.py
```

Result: **138 passed, 5 failed, 1 warning**. Existing failures remain in WhatsApp routing/foreground behavior and local application window verification/website alias resolution; none are in changed search paths. Both affected files already had baseline failures. The complete 71-file baseline suite was not rerun.

Compilation: passed for all modified Python modules. Live provider verification is documented in [SEARCH_PROVIDER_HEALTH_REPORT.md](SEARCH_PROVIDER_HEALTH_REPORT.md); only Bing fallback was live verified in this environment.
