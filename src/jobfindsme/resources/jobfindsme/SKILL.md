---
name: jobfindsme
description: Find, compare, save, and track jobs with the local JobFindsMe engine.
---

# JobFindsMe

Use JobFindsMe when the user wants to discover, compare, save, track, export,
monitor, or delete job-search data.

## Privacy

- Never read, paste, summarize, or copy the complete resume into model context.
- Pass the local resume path to `setup_profile`.
- If the host cannot access that path, ask the user to run
  `jobfindsme profile import <path>` and continue from the confirmed profile.
- Return only confirmed profile facts and the minimum evidence needed.

## Workflow

1. Reuse an existing Workspace and Search Plan when available.
2. Ask only for missing constraints that materially change results: target role,
   location, salary boundary, experience boundary, or explicit exclusions.
3. Call `setup_profile` with `action: import`, review the proposed facts with
   the user, then call it with `action: confirm`.
4. Call `search_jobs` with explicit public or local sources when discovery is
   needed; use `get_jobs` to inspect stored source evidence.
5. Compare jobs using source, liveness, score, reasons, warnings, and apply URL.
6. Use `update_job_state` only after the user states the desired change.
7. Use `configure_monitor` only after explicit opt-in.
8. Use `export_local_data` when the user asks for a portable local export.

## Deletion

Deletion always takes two separate calls:

1. Call `delete_local_data` with `action: preview`.
2. Show the exact scope and counts to the user.
3. Ask for explicit confirmation.
4. Only then call it again with `action: confirm` and the returned token.

Never invent, reuse, or bypass a confirmation token.

## Boundaries

- Treat Core results as facts; do not invent jobs, salary, freshness, or links.
- Clearly label unknown salary or freshness.
- Do not claim that a synthetic evaluation score is field performance.
- Do not automate applications or external messages.
