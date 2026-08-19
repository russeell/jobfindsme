# Agent Behavior Evaluation

Python tests prove that Core and MCP functions are correct. This suite proves a
different property: an Agent that receives the Skill follows the intended user
workflow.

## Fixed acceptance prompts

`cases.json` covers eight release-critical behaviors:

1. one sentence triggers `setup -> search_jobs`;
2. the five-section Server output and bare apply links stay intact;
3. cache use and source failure stay visible with a chat-based recovery action;
4. “mark job 2 as applied” calls `update_job_state` correctly;
5. incremental search suppresses jobs already shown;
6. the Agent passes a resume path to Core instead of reading the full resume.
7. a changed city updates preferences before searching again.
8. a recommendation explanation is grounded in a requested job's evidence.

## RED then GREEN

The deterministic fixtures keep the Skill contract under CI:

```bash
python -m evaluation.agent_behavior.cli \
  --cases evaluation/agent_behavior/data/cases.json \
  --transcripts evaluation/agent_behavior/data/fixtures/baseline.json \
  --report /tmp/jobfindsme-agent-red.json \
  --expect fail

python -m evaluation.agent_behavior.cli \
  --cases evaluation/agent_behavior/data/cases.json \
  --transcripts evaluation/agent_behavior/data/fixtures/with_skill.json \
  --report /tmp/jobfindsme-agent-green.json \
  --expect pass
```

The baseline must fail and the Skill fixture must pass. Both are
`contract_fixture` evidence: they test the evaluator and the behavioral
contract, not a live model.

## Release evidence

Before claiming cross-Agent compatibility, record normalized transcripts from
Codex, Claude, and Cursor with `evidence_kind: live_agent`, then run:

```bash
python -m evaluation.agent_behavior.cli \
  --cases evaluation/agent_behavior/data/cases.json \
  --transcripts reports/agent-behavior/live-vX.Y.Z.json \
  --report reports/agent-behavior/live-vX.Y.Z-report.json \
  --expect pass \
  --require-evidence live_agent \
  --require-host codex \
  --require-host claude \
  --require-host cursor
```

Each transcript is an ordered event stream containing only `assistant`,
`tool_call`, `tool_result`, `file_read`, and `shell` events. Redact personal
data, cookies, local IDs, and resume contents. If a host cannot be run, report
it as blocked; do not replace live evidence with a fixture.
