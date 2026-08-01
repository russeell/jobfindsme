# Connectors

Only two source paths are maintained:

| Source | Primary path | Fallback | Role |
|---|---|---|---|
| BOSS直聘 | authorized local Chrome CDP | recent labeled cache | primary live source |
| 猎聘 | HTTP JSON (curl_cffi) | bounded CDP detail enrichment, then cache | independent second source |

## BOSS直聘 (Chrome CDP)

- Requires a user-authorized local Chrome session started by
  `jobfindsme setup` (dedicated profile, port 9222).
- The connector never touches the user's personal Chrome profile;
  it only manages its own process (PID file, reachability probe).
- Search results are fetched by injecting `resources/connectors/boss_fetch.js`
  into the live page (XHR capture with `credentials: include`), giving full
  job descriptions and skill signals.
- A 401/403 response is reported as `authentication_required` — the
  recovery action is `jobfindsme setup` and re-login.

## 猎聘 (pure HTTP)

- Uses `curl_cffi` against `api-c.liepin.com`; no browser required.
- Platform limitation: the HTTP listing does not include JD body text —
  bounded browser enrichment may fill descriptions, otherwise the JD body
  is absent and matching falls back to title/card signals.
- `mark_missing_closed` marks previously-seen jobs closed when they
  disappear from the listing.

## Source health

- Sources run concurrently with bounded timeouts; one source failing
  never cancels the other's results.
- Every run records status (success / degraded / failed / skipped),
  duration, discovered/unique counts, cache usage, and a bounded error.
- A failed browser refresh with cached records degrades gracefully;
  with no cache it fails and is shown as such (never as "no new jobs").
- Retired source kinds (`zhilian_cdp`, `lagou_cdp`, `wuyou_cdp`,
  `liepin_cdp`) remain readable in old databases but are never
  selected, executed, or documented as supported.

## Caching

The job repository keeps recent labeled cache per source. Cache-mode
search (`refresh_mode: cache`) performs no remote access at all.

Full engineering constraints: see `docs/internal/project_spec.md`
(Source strategy section).
