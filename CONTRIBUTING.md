# Contributing

Confirmed BOSS applications use a dedicated executor, separate from the read-only
research browser. Preserve immutable material snapshots, exact chosen resume
bytes/versions, persistent reservations, per-source pauses and independent message
and attachment receipts. A click or an optimistic message bubble is not success.
Test duplicate confirmations, changed recipients/files, missing upload controls,
cancel/challenge/timeout, failed server rereads and restart recovery with fictional
fixtures. A simulated browser transport can validate UI/IPC/database integration,
but cannot establish live platform compatibility or delivery. Obtain explicit
approval for the specific employer, message and resume before a real submission;
keep live checks bounded and stop on platform verification or rate limits.

Help people find relevant jobs, prepare truthful materials, and understand what
actually happened. Prefer improvements to this complete workflow over adding
another disconnected feature.

Start with the [README](README.md), [current status](docs/desktop/HANDOFF.md),
[module map](docs/desktop/STRUCTURE.md), and [task list](docs/desktop/tasks.json).
The maintained product is the local desktop app. Historical prototypes and
archived plans are references, not the current implementation.

## Development

Use Python 3.11–3.13 and Node.js 22. From the repository root, create and activate
a virtual environment, then install the development dependencies:

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -e ".[dev]"
cd apps/desktop
npm ci
npm run build
```

On Windows, activate `.venv\Scripts\Activate.ps1` in PowerShell. The desktop app
needs its local Python service; see the [desktop entry point](docs/desktop/README.md)
and package scripts for the supported launch and packaging paths.

Keep changes focused. Preserve database migrations, original resume files,
existing sessions, drafts, and records. Reuse the existing connectors, document
model, API contracts, and SQLite services before introducing a new subsystem.
Keep personal development skills, build output, and test artifacts out of Git;
application skills and required third-party license notices must remain.

Local personal information must stay local: resumes and extracted content,
account identifiers, conversations, drafts, databases, credentials, cookies,
browser profiles, and private logs/screenshots. Use fictional fixtures for CI,
external model tests and shared evidence. Review the staged diff before an
authorized push; do not upload personal material to reproduce a bug. Redaction
alone is not permission to transmit a user's information. Preserve original
files and sessions; do not delete them to satisfy a packaging check.

## What a good change delivers

| Area | Required behavior |
| --- | --- |
| Search | Relevant results, explicit source coverage, stable continuation, and partial results preserved when another source fails. Unknown fields remain unknown. |
| Login and JD | Login recognition, list retrieval, pagination, and complete JD extraction are separate capabilities. A visible website or a successful HTTP status proves none of the others. |
| Resumes | Import displays the original; extraction happens locally in the background. Editing creates a copy. Supported styles survive saving and export; complex layout conversion has clear limits. |
| Material reuse | JD, explicitly selected resume, interview context, greeting, and application records refer to the same workspace and job. Later edits must not silently change previously used materials. |
| AI | Changes are grounded in supplied experience, explain their purpose, and can be reviewed or undone. Unchanged output is not a successful improvement; missing facts must not be invented. |
| UI | Main actions are visible and appropriate to the current stage. Preserve input and reading position, show task progress, and offer recovery beside the failing operation. |
| Applications | Opening a page, filling a form, clicking send, and confirmed delivery are different outcomes. Opening an original page must never mark a job as applied. |

## Verification

Run the checks that can catch the failure introduced by your change. Do not add
implementation-mirroring tests or repeat a full suite for a documentation edit.
For example, after activating the environment:

```bash
# Python connector and search contract changes
python -m pytest tests/connectors/test_pure_http.py tests/desktop_api/test_source_search.py
ruff check .
ruff format --check .

# Desktop changes, from apps/desktop
npm run build
node --test tests/source-presentation.test.mjs
```

Use the related resume, preparation, or desktop tests for those modules. Full
Python/desktop suites and matching evaluation gates belong at integration and
release boundaries. Existing CI covers supported hosts; passing mocked tests
is not evidence of live platform availability.

For UI changes, check the actual application at normal and narrow window sizes,
with the browser pane open when relevant. Check scrolling, keyboard access,
switching pages during work, cancellation, retries, and restart recovery.
Resume changes should exercise import → original display → edit → save → preview
→ Word/PDF export → restart, using fictional files. Inspect exported content and
layout, not only whether a file was created.

## Live platform acceptance

Use a small, bounded query only when real evidence is missing or an affected
connector changed. Reuse the user's authorized session; never copy cookies or
credentials into fixtures. Login and verification challenges require user action.
Stop the affected source at a challenge and preserve other sources' results.
Reuse cached checks, listings, and JDs before accessing a platform again. Keep
requests serialized per source, respect cooldown and backoff, and avoid repeated
refreshes or retry loops. Only an observed new login may trigger an early login
check; an unverified status alone must not reset the cooldown. No fixed request
interval guarantees that a platform will not restrict an account.

Record the application version/source commit, test time, platform, keyword and
city, then distinguish:

- Login observed and correctly recognized; session persists after restart.
- Search scope matches the request; record first usable result time and total time.
- Sampled titles, companies, locations and salary periods agree with original pages.
- Complete JD belongs to the exact selected job and includes its responsibilities
  and requirements, rather than a list summary or recommendations.
- A continuation page adds jobs without losing or duplicating previous results.
- Login expiration, verification, timeout, empty results, and parsing failures
  produce different outcomes with a usable recovery action.

State sample counts and evidence limits. One successful query is not whole-site
coverage; a cached result is not a new live test. Keep current findings in the
handoff/task list instead of creating another historical evidence directory.

Do not submit real applications during testing. Paid model calls and external
transmission of private material need explicit user authorization for that
specific transmission; a standing no-upload instruction takes precedence over
earlier permissions. Use fictional fixtures; never commit personal resumes, phone numbers,
email addresses, databases, API keys, browser profiles, or raw authenticated logs.

## Changes and releases

Explain the problem, resulting behavior, relevant verification, and remaining
limits in a focused contribution. Link reproducible issues when available and
check the license before copying code or adding a dependency.

Release packages must be built and tested from the same source commit, record
that commit and version inside the package, pass the frozen-runtime audit, and
include SHA256 checksums. Verify the actual macOS/Windows artifacts contain no
user or test data. Publishing a release is a separate, explicitly authorized step.

Use the [reproducible packaging instructions](docs/desktop/README.md#可重复打包与实际包验收).
Release Python 3.13 uses the hashed `requirements/release.txt`; install the project
with `--no-deps --no-build-isolation` after installing that lock. Node and package
smoke tooling use `npm ci`; do not install unpinned test tools during release.
The freeze wrapper and desktop build record source/dependency fingerprints, and
packaging refuses stale or uncommitted production inputs. Ordinary CI and
on-demand package workflows are separate. Cache downloaded dependencies only,
never a user profile or a previously frozen application. A tag builds artifacts;
it does not publish a Release. Test both hosts at the exact same commit before
using the separately authorized attachment/publishing workflows.

Both package audits run the same privacy check before artifacts can be shared.
SQLite files and sidecars, browser storage, credential files and resume documents
are rejected; required licenses, application skills and named dependency resources
are allowed. Package links must resolve within the bundle. CI uploads only the
named ZIP and checksum after the complete verification succeeds, never wildcard
logs or screenshots. These checks supplement review; they cannot detect private
content deliberately disguised as application code or a permitted public asset.

The project is licensed under [MIT](LICENSE). Contributions remain yours; by
submitting a contribution for inclusion, you agree to license it under MIT.
