# jobfindsme · AI Job Search Radar

**One sentence brings together jobs from BOSS直聘, 猎聘 (Liepin), 智联招聘 and 前程无忧, then filters and tracks them against your resume.**

[Chinese](README.md) · [Install](INSTALL.md) · [Architecture](docs/architecture.md)

> ⭐ If jobfindsme saves you time, give it a star so more job seekers can find it.

## What it does

- searches **BOSS直聘、猎聘 (Liepin)、智联招聘、前程无忧** from one Agent;
- deterministically ranks jobs against structured local resume facts;
- returns matching jobs with direct apply links;
- host-Agent scheduled searches; applied jobs are never re-suggested;
- query every job ever matched, with its state.

## Install

Install the local runtime once:

```bash
curl -fsSL https://cdn.jsdelivr.net/gh/russeell/jobfindsme@main/scripts/install.sh | bash
```

Then install the native Agent plugin:

```bash
# Codex
codex plugin marketplace add russeell/jobfindsme --ref main
codex plugin add jobfindsme@jobfindsme

# Claude Code
claude plugin marketplace add russeell/jobfindsme
claude plugin install jobfindsme@jobfindsme
```

The Cursor manifest is maintained in this repository. Until its marketplace
listing is approved, use `jobfindsme connect cursor`. Other MCP clients can use
`jobfindsme config` or `jobfindsme connect --path <file>`. See
[INSTALL.md](INSTALL.md) for upgrades and fallback installation.

## Use

```text
Use jobfindsme and my local resume at ~/Documents/resume.pdf
to find full-time AI application engineer roles in Shanghai and Hangzhou,
20K+ monthly salary, experienced hiring.
```

Later:

```text
Find new jobs since my last search.
```

## Sources

Four source paths are maintained — **BOSS直聘**, **猎聘 (Liepin)**,
**智联招聘**, and **前程无忧**.
The project prioritizes useful, reliable results over an inflated connector
count and does not claim complete market coverage.

| Source | Method | Speed | Browser needed? |
|---|---|---|---|
| BOSS Zhipin | authorized local Chrome CDP, asynchronous site response in page context | ~0.5s | ✅ yes (login session) |
| Liepin | `api-c.liepin.com` pure HTTP JSON API | ~1.0s | ❌ no |
| Zhaopin | public web JSON API, bounded CDP fallback | varies | usually no |
| 51job | public web JSON API, bounded CDP fallback | varies | usually no |

HTTP sources can degrade to an explicitly labeled recent cache when challenged.
When Chrome is available, bounded browser fallbacks may enrich results. BOSS
requires an authenticated local Chrome session.

## Privacy and limitations

- resumes, plans, and job state remain in local SQLite;
- the Agent receives a resume path, not the complete resume text;
- job descriptions are untrusted external content;
- the ranking score is explainable and reproducible, not a hiring probability;
- the project does not auto-apply or guarantee complete market coverage.

See [architecture](docs/architecture.md) for the module map and the
search path, [connectors](docs/connectors.md) for source promotion
gates, and [evaluation](docs/evaluation.md) for the quality loop. The
full engineering spec lives in `docs/internal/project_spec.md`.

## License

[MIT](LICENSE)
