# Evaluation

Evaluation is a development-time quality gate, not a production path.
It lives in the same repository because it participates in CI, but the
dependency direction is one way:

```text
Evaluation → production Core
Core ✗→ Evaluation
```

## Layout

| Path | Role |
|---|---|
| `evaluation/datasets/` | synthetic dataset builder, search-result collection, labeling templates |
| `evaluation/metrics/` | `evaluate_dataset` / `evaluate_chinese_dataset` and reports |
| `evaluation/regression/` | snapshot replay (`save/load/replay`) and the frozen legacy BM25 matcher |
| `evaluation/field_trial/` | live search loop, field-trial dataset assembly, improvement analysis |
| `evaluation/cli.py` | evaluation entry (`python -m evaluation.cli`) |

`evaluation` lives at the repository root and is deliberately excluded from
the installed wheel; it is a development-time tool, never a runtime import.

## Gates

- `pytest` — full suite (CI runs it on Python 3.11/3.12/3.13)
- `ruff check .` and `ruff format --check .`
- Synthetic evaluation regression gate (CI):
  `python -m evaluation.cli --dataset evaluation/data/v0.1.json --report <tmp>/synthetic-evaluation.json --type synthetic`
- `scripts/smoke_installed_package.sh` — built wheel sanity

## Claims policy

- Public quality claims must come from a **manually labeled** real
  snapshot (EVAL-001), never from synthetic data.
- Metrics produced: P@10, NDCG@10, valid-link rate, source success
  rate, latency, hard-filter false-negative rate.
- Live-loop reports contain only a profile hash and compact signals —
  never resume content.

## Skill taxonomy

Skills and aliases live in `src/jobfindsme/resources/taxonomy/skills.json`:

1. Add a canonical skill and its real-world aliases.
2. Do not reuse an alias owned by another skill.

## Agent behavior

Core and MCP unit tests do not prove that a host Agent selects the right tools
or grounds its answer in the Server facts. `evaluation/agent_behavior/data/`
therefore treats the canonical Agent Skill as executable behavior:

- eight fixed prompts cover first search, factual output (every apply URL
  preserved, nothing invented), apply links, source degradation, applied
  state, incremental search, resume privacy, city changes, and recommendation
  explanations;
- the no-Skill fixture must fail and the Skill fixture must pass in CI;
- fixture reports are marked `contract_fixture` and cannot satisfy a
  `live_agent` evidence gate;
- release compatibility claims require redacted Codex, Claude, and Cursor
  transcripts.

## Four-layer verification (not "use it for a week")

Product correctness is proven by compressed-time assets instead of waiting
for a week of dogfooding:

1. **Multi-day Radar replay** — `evaluation/regression/radar_replay.py` replays
   deterministic Day 1/2/3 fixtures (`evaluation/data/radar_replay/`) through
   the real pipeline and verifies new / changed / closed / suppressed /
   applied-suppression transitions in minutes.
2. **Golden matching dataset** — `evaluation/data/golden/golden_v1.json`
   (40 labeled jobs, built by `scripts/build_golden_dataset.py`) plus
   `evaluation/metrics/golden_runner.py`. Headline metrics are Recall@20 and
   hard-filter False-Negative rate; the gate runs in CI. Rebuild with
   `python -m evaluation.cli --dataset evaluation/data/golden/golden_v1.json
   --report /tmp/golden.json --type golden`.
3. **Real-platform comparison** — `scripts/platform_compare.py` runs a real
   search and dumps CSV; manually sample the same query on BOSS直聘/猎聘 and
   classify coverage / filter / ranking gaps.
4. **Agent behavior** — fixed prompts (now 8 cases, including city change and
   recommendation explanation) prove the Skill maps user language to correct
   MCP calls; the no-Skill baseline must fail and the Skill fixture must pass.

Real dogfooding still matters, but only for things lab tests cannot see
(platform outages, dirty state over time, UX friction, systematic miss
patterns) — it is no longer the gate.

See `evaluation/agent_behavior/data/README.md` for commands and the normalized event
schema.
3. Run `python -m scripts.validate_taxonomy` and
   `python -m pytest tests/test_taxonomy.py`.
4. Include one realistic resume or job-description example in the PR.

The default matcher remains deterministic and requires no model API.
Semantic matching can be added later as an optional, separately
evaluated provider.
