# Live internet search and voice recovery — 6 October 2026

## Understanding and plan

The reported `1006 abnormal closure` followed a WebSocket keepalive ping timeout in the runtime log. The existing reconnect loop reopened sockets, but requested resumption without retaining the server handle. The existing web search was registered; its string return could mark an unsuccessful search as a successful tool call. Bing tracking URLs were reported as source domains, and a real public query briefly returned unrelated generic news. Some current-fact questions reached static knowledge before search.

Extend the existing shared voice/chat pipeline and provider fallbacks. Keep authentication, confirmations, microphone echo protection and bounded retry behavior. Do not replay laptop actions after a disconnect.

## Implementation

- Route current/explicit English, Hinglish and Hindi lookups before static knowledge. Keep ordinary study questions and local calculations off forced search.
- Register a structured web handler that retains actual success/failure, verification, source results, retrieval timestamp and recent-cache status. Current queries bypass cache, including Hindi/Hinglish time markers. Search failure produces an honest Hinglish response.
- Decode DuckDuckGo/Bing tracking wrappers locally into actual HTTP(S) source links. Reject malformed, credential-bearing and literal private/local links. Sanitize untrusted result text, deduplicate links and cap result counts. Scraper topic filtering discards clearly unrelated results before another fallback; it is a simple relevance check, not factual verification.
- Upgrade the obsolete `duckduckgo-search` dependency to its maintained `ddgs==9.16.0` replacement. Preserve optional Google Custom Search, Serper and Brave configurations plus keyless fallback search. Respect TLS verification and existing account authentication.
- Retain resumable server handles only in memory for at most two hours; use sliding-window context compression. Handle GoAway and an empty closed receive stream by renewing the socket instead of spinning. A rejected resumed connection retries fresh, and an unsupported model clears its handle before fallback.
- Clear pre-action resumption state before tool execution so an uncertain outgoing operation is not resumed from an earlier snapshot. Preserve the bounded retry/local fallback and typed-context routing. Display a plain reconnect notice for transient socket errors and a connected notice after recovery; genuine errors remain diagnostic information.
- Align the base prompt with continuous conversations and require real returned sources for internet answers.

## Tests and real verification

Final affected regression suite: **499 passed, 1 warning in 63.70 seconds**. Dedicated coverage checks current-versus-static routing, source decoding, unsafe source rejection, failure propagation through chat/voice, freshness/cache behavior, scraper relevance, retained/expired resume state, graceful renewal, pre-action token invalidation and rejected-token recovery. Existing isolated Qt/WebChannel, communication, speech, memory, security and daily companion checks remain included.

Actual public lookup: `latest Python release official documentation` returned relevant `python.org` and `docs.python.org` sources with direct links. With the first two provider paths deliberately unavailable, the installed DDGS fallback also returned relevant official Python sources. Evidence: `scratch/live_search_recovery_probe.json` and `scratch/ddgs_fallback_probe.json`.

A neutral provider test connected with the same Live model, Charon and compression, received a real resumable handle and connected again with that handle. No microphone recording or speaker playback was used for that probe, and no contact was messaged/called or power operation executed. Resumption handles and API credentials are never written to the evidence file.

Final patched JARVIS restarted as PID 13844. Fresh health samples confirmed the live session connected, microphone capture enabled, increasing audio frames (386 sent at the last sample) and zero send errors. Startup natural TTS returned HTTP 200; capture paused for playback and resumed afterward. Evidence: `scratch/live_search_recovery_runtime_check.json`.

The optional native Gemini Google-grounding probe returned a quota error (429), so that unavailable path was not added. Working public search does not require it. Earlier legacy web-first tests assume plain WhatsApp always opens its website; current user-requested behavior is desktop first with explicit Web/Chrome routes separate. The relevant Chrome routing assertions were updated to check those exact routes, preserving strict expectations. Two unrelated legacy web-first app-mapping checks remain outside this affected regression suite; they do not describe the current desktop-first architecture.

## Review and limits

Internet/provider outages and quota limits can still occur; this repair supplies recovery and truthful failure reporting, not a guarantee that a remote socket can never close. Search snippets and retrieval timestamps do not establish that every factual claim is current or correct. A provider can omit publication dates. Mic transport checks are distinct from a physical multi-turn speech recognition test. Timetable and contact/call behavior were not expanded in this change.

Official references used for the implementation: [Gemini session management](https://ai.google.dev/gemini-api/docs/live-api/session-management), [WebSocket keepalive](https://websockets.readthedocs.io/en/stable/topics/keepalive.html), and [DDGS package/API documentation](https://pypi.org/project/ddgs/).
