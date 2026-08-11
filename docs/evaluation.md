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
  `python -m evaluation.cli --dataset data/eval/v0.1.json --report <tmp>/synthetic-evaluation.json --type synthetic`
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
or preserves the Server response. `evaluation/agent_behavior/data/` therefore treats the
canonical Agent Skill as executable behavior:

- six fixed prompts cover first search, five-section output, apply links,
  source degradation, applied state, incremental search, and resume privacy;
- the no-Skill fixture must fail and the Skill fixture must pass in CI;
- fixture reports are marked `contract_fixture` and cannot satisfy a
  `live_agent` evidence gate;
- release compatibility claims require redacted Codex, Claude, and Cursor
  transcripts.

See `evaluation/agent_behavior/data/README.md` for commands and the normalized event
schema.
3. Run `python -m scripts.validate_taxonomy` and
   `python -m pytest tests/test_taxonomy.py`.
4. Include one realistic resume or job-description example in the PR.

The default matcher remains deterministic and requires no model API.
Semantic matching can be added later as an optional, separately
evaluated provider.
