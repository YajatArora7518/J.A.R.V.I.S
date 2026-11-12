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

Compilation: passed for all modified Python modules. Live provider verification is documented in [SEARCH_PROVIDER_HEALTH_REPORT.md](SEARCH_PROVIDER_HEALTH_REPORT.md); only Bing fallback was live verified in that environment.

## Final audit addendum (2026-11-12)

A static re-audit was performed on branch `audit/final-search-audit-20261112`; full findings are in [JARVIS_FINAL_SEARCH_AUDIT_20261112.md](JARVIS_FINAL_SEARCH_AUDIT_20261112.md).

- Test status for this audit session: **NOT RUN**. The audit was a static code review with no Python runtime attached; pytest was not executed. No test was hidden, deleted, weakened, or modified in any way.
- Baseline comparison: the 42 passed (focused) and 138 passed / 5 failed / 1 warning (regression) figures above remain the saved 2026-11-07 baseline. The audit made zero code changes, so no new regression can originate from it. If a local re-run shows failures beyond the known 5 (in `tests/test_web_automation.py` and `tests/test_web_first_master.py`), investigate and compare against the saved baseline rather than adjusting the tests.
- Re-verified statically: the asserted behaviors (retry policy bounds, circuit breaker thresholds, dedup/ranking, date distinctions, registry count of 73, `web_search_structured` signature) are present in the implementation files listed in [COMBINED_STAGE_2_2_STAGE_3_REPORT.md](COMBINED_STAGE_2_2_STAGE_3_REPORT.md).
- Rollback of this addendum: delete this section or do not merge the audit branch. No implementation or test file was changed by the audit.