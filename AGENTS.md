# JobFindsMe — Desktop Refactor Instructions

## Active development direction (2026-09-18)

The user has approved automatic staged implementation of a local desktop
job-search product and retirement of the MCP product surface. The authoritative
development documents are:

- `docs/desktop/REFACTOR.md`: product scope and migration boundaries.
- `docs/desktop/TECHNICAL.md`: proposed architecture and data contracts.
- `docs/desktop/DEVELOPMENT.md`: task selection, verification and handoff.
- `docs/desktop/tasks.json`: task dependencies, status and acceptance evidence.

For desktop refactor work, these documents supersede conflicting legacy rules
below (MCP retention, host-owned scheduling, optional resume use and distribution).
D47 explicitly authorizes conservative directory grouping and removal of the old
plugin marketplace manifests. Retain CLI/MCP commands and resources until their
external entrypoints and CI are deliberately retired; see STRUCTURE.md.
Use `.agents/skills/jobfindsme-dev/SKILL.md` for incremental development.
The approved UI reference is `docs/desktop/ui/jobfindsme-desktop.html`; later
requirements in the desktop plan take precedence over mock interactions.
Do not add human-review gates. Use an independent AI review in a new session
only for material risk or unresolved implementation questions; see the skill.
Implementation status is recorded only in `docs/desktop/tasks.json`.
Use targeted risk-based checks; do not repeat full suites for each small edit.
Git policy (user authorization, 2026-09-21): establish a verified local baseline,
then commit each independent fix after its relevant checks pass. Work on
`codex/desktop-refactor`; preserve existing history and user changes. Record
verification and known limitations in desktop evidence. Never automatically
push, publish, or create a release. Exclude credentials, login profiles, private
resumes and generated build artifacts. This policy supersedes legacy Git rules.

## Current structure and compatibility

Read `docs/desktop/STRUCTURE.md` for exact paths and preserved boundaries.
Python search lives in `search/`, source catalog/admission in `sources/`.
Electron main is grouped into browser/sources/backend/security; renderer business
components live in search/research/resume/settings with common UI in shared.
Keep App.tsx and main/index.ts as composition roots; do not split large files as
an incidental part of directory maintenance. Shared desktop contracts stay in
apps/desktop/shared; Python business contracts stay in contracts/.

CLI/MCP behavior remains defined by `skills/agent-job-search/SKILL.md`; generate
its wheel mirror with `python scripts/sync_skill.py` if it changes. Retained
compatibility commands and history readers still need their regression tests.
Legacy docs live in docs/legacy and do not override desktop product decisions.
Never delete migrations, private user data or unknown untracked files for a
shorter tree. No live account actions, paid model calls or real applications
without explicit user authorization. No recurring automation for D47.
