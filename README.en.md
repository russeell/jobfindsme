# JobFindsMe

Let an existing AI agent discover, match, and track jobs using local resume facts
and public job sources.

- Local-first SQLite workspace
- Complete deterministic workflow without a model API
- MCP integrations for Codex, Claude Code, Qwen Code, and compatible clients
- Profile-to-job evidence for every skill-based recommendation
- Subscription-backed discovery and optional local monitoring

[中文](README.md)

## Install

```bash
python3 -m pip install "jobfindsme @ git+https://github.com/russeell/jobfindsme.git"
jobfindsme doctor
jobfindsme install codex  # or claude / qwen
```

Restart the agent and ask:

```text
Use JobFindsMe with ~/Documents/resume.pdf.
Find AI application engineer roles in Shanghai from official sources.
Exclude outsourcing and on-site contracting.
```

Workspace and Search Plan IDs are internal. JobFindsMe creates and resolves the
active context automatically.

## Supported Sources

| Source | Status |
|---|---|
| Public Greenhouse Job Board API | Available |
| Single-job Schema.org `JobPosting` page | Available |
| User-provided CSV / JSON | Available |
| Sources requiring login, CAPTCHA, or anti-bot bypass | Unsupported |

The current release does not provide a public Web service or automatic job
applications.

## Safety

- The host agent passes a resume path instead of reading the complete document.
- Job descriptions are untrusted external data and are summarized by default.
- Full details require an explicit single-job request.
- Exports are written locally; the agent receives only a path, hash, and counts.
- Deletion always requires preview followed by a short-lived confirmation token.
- Redirect targets are validated before every HTTP connection.

Synthetic datasets are regression evidence, not field-performance claims.
See [`PROJECT_SPEC.md`](PROJECT_SPEC.md) and [`reports/`](reports/).

Licensed under the [MIT License](LICENSE).
