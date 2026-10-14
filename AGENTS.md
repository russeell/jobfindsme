# JobFindsMe development notes

This repository's current product is the local desktop application. Start with
`README.md`, `docs/desktop/HANDOFF.md`, `docs/desktop/STRUCTURE.md` and
`docs/desktop/tasks.json`. Historical refactor plans and QA attachments remain
in Git history, not the current file tree. Do not revive behavior from them.

Product priorities: real and relevant job results, honest source status, original
job pages, evidence-backed role research, and a lightweight confirmed resume.
Scheduled search is disabled. A website opening is not proof that its listings,
pagination or full job descriptions can be extracted. Never automatically apply
for jobs or use paid model calls without explicit user authorization. Preserve
user sessions, local data and every database migration.

Do not upload local personal information. Resumes (including redacted extracts),
account identifiers, chats, drafts, databases, credentials, cookies, browser
profiles, and private logs/screenshots must stay local. Earlier model or platform
permissions do not authorize new transmissions of these materials. Use fictional
fixtures for CI, external model tests and shared evidence. Review staged changes
and package contents before any authorized upload; upload only reviewed source,
public assets and verified packages containing no user data. Preserve local
originals and sessions rather than deleting them to make an upload pass.

Work on `codex/desktop-refactor` unless the user chooses another branch. Keep
independent fixes small, run checks appropriate to the affected code, and commit
each verified fix. Fetch and merge the current remote main before integrating;
never force-push or overwrite remote work. The user prefers direct integration
into main. Use an English pull request only when direct integration is blocked
by repository rules or approval review. Do not publish packages or releases
without separate authorization.

Keep the current tree focused on working code, tests, packaging and concise
current docs. For history, link to a fixed Git commit instead of restoring old
plans or per-task evidence files. Personal development skills stay local;
application skills and their license notices remain in `apps/desktop/skills/`.
