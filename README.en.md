# jobfindsme · AI Job Search Radar

**Search several job sources from one Agent, match jobs against a local resume,
and focus later searches on new opportunities.**

[Chinese](README.md) · [Install](INSTALL.md) · [Specification](PROJECT_SPEC.md)

## What it does

- searches BOSS Zhipin, Liepin, Zhaopin, and 51job from one Agent;
- filters location, salary, experience, recruitment track, and employment type;
- returns a ranking score, resume evidence, gaps, and a direct job link;
- remembers seen, saved, dismissed, and applied jobs;
- reports new and materially changed jobs on later searches.

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
  "jobfindsme[browser] @ https://github.com/russeell/jobfindsme/releases/download/v0.3.0/jobfindsme-0.3.0-py3-none-any.whl"
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

Each source uses a three-tier fallback chain — pure HTTP first (sub-second),
then CDP interception, then DOM extraction:

| Source | Pure HTTP | Browser fallback | Role |
|---|---|---|---|
| BOSS Zhipin | — | authenticated local CDP | primary live source |
| Liepin | ✅ `api-c.liepin.com` JSON, ~0.9s | CDP → DOM | sub-second, no browser |
| Zhaopin | ⚠️ honeypot-detected | CDP interception → DOM | additional candidates |
| 51job | ⚠️ WAF2-detected | CDP interception → DOM | additional discovery |

Lagou was retired from live discovery because verification failures, incomplete
fields, and latency outweighed its observed value. Existing historical records
remain readable.

The source strategy is layered: pure HTTP direct API first (sub-second,
no Chrome), CDP passive interception when the platform's anti-bot wall blocks
direct HTTP, and DOM extraction as the final fallback. The project does not
treat signature reverse engineering or CAPTCHA bypass as a supported path.

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
