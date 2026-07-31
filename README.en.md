# jobfindsme · AI Job Search Radar

**One sentence searches BOSS直聘 and 猎聘 (Liepin) together, matching jobs against your resume.**

[Chinese](README.md) · [Install](INSTALL.md) · [Specification](PROJECT_SPEC.md)

## What it does

- searches **BOSS直聘** and **猎聘 (Liepin)** from one Agent;
- matches jobs against your resume (Agent-side semantic ranking);
- returns matching jobs with direct apply links;
- optional scheduled push at any time/frequency; applied jobs are never re-suggested;
- query every job ever matched, with its state.

## Install

Ask the current Agent:

```text
Follow this installation recipe exactly. Detect which Agent host you are.
Do not clone the repository or run its tests:
https://github.com/russeell/jobfindsme/blob/main/INSTALL.md
```

Or install manually:

```bash
python3 -m venv ~/.jobfindsme/runtime
~/.jobfindsme/runtime/bin/python -m pip install \
  "jobfindsme[browser] @ https://github.com/russeell/jobfindsme/releases/download/v0.5.0/jobfindsme-0.5.0-py3-none-any.whl"
~/.jobfindsme/runtime/bin/python -m jobfindsme connect claude
~/.jobfindsme/runtime/bin/python -m jobfindsme setup
```

Replace `claude` with `codex`, `workbuddy`, `kimi`, `trae`, `zcode`, `qwen`,
`qoder`, or `trae-cn`. Every Agent uses the same runtime; only its MCP config
path differs.

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

Two platforms only — **BOSS直聘** and **猎聘 (Liepin)**, covering the large
majority of China's tech hiring market. The focus keeps maintenance cost and
failure rate low.

| Source | Method | Speed | Browser needed? |
|---|---|---|---|
| BOSS Zhipin | local Chrome CDP, XHR-injected internal API | ~0.5s | ✅ yes (login session) |
| Liepin | `api-c.liepin.com` pure HTTP JSON API | ~1.0s | ❌ no |

Liepin prefers pure HTTP (sub-second, no browser). When Chrome is available,
the browser tier additionally enriches job detail pages with JD text for stronger
matching signals. BOSS requires an authenticated local Chrome session.

## Privacy and limitations

- resumes, plans, and job state remain in local SQLite;
- the Agent receives a resume path, not the complete resume text;
- job descriptions are untrusted external content;
- the ranking score is explainable and reproducible, not a hiring probability;
- the project does not auto-apply or guarantee complete market coverage.

See [PROJECT_SPEC.md](PROJECT_SPEC.md) for architecture, evaluation, and source
promotion gates.

## License

[MIT](LICENSE)
