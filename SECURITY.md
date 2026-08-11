# Security

jobfindsme is local-first by design: resumes, job data, search plans,
and tracking state live in a local SQLite database on your machine.

## Privacy guarantees

- **Resumes are parsed locally.** The complete resume text never enters
  the Agent context and is never stored — only structured facts
  (skills, experience, education) and minimal evidence snippets are kept
  in SQLite. The source file is forgotten by default
  (`forget-source` mode).
- **Job descriptions are untrusted data.** Every JD returned by a
  source is treated as external content, never as instructions. The
  `untrusted_external_content` flag marks it for hosts.
- **No account, no telemetry, no cloud.** The engine works without a
  model API key; there are no hosted services.

## Browser bridge isolation

- BOSS直聘 access runs through a dedicated Chrome profile started by
  `jobfindsme setup` — the connector never opens, kills, or touches
  your personal Chrome profile.
- The connector manages only its own process (recorded PID), and a
  reachability probe avoids relaunching an already-running bridge.

## Data control

- **Export** (CLI `jobfindsme export`) writes a local file and returns
  only its path, SHA-256 hash, and record counts. The file stays on
  your machine.
- **Deletion** (`delete_local_data`) is a two-phase protocol: preview
  first, then confirm with a short-lived, single-use token. Deletion is
  irreversible.

## Transport

- MCP runs over stdio only — no network listeners, no ports opened by
  the server itself (the Chrome bridge aside).

## Reporting

If you find a security issue, open a private report via the repository's
Security tab or file an issue without including personal data.
