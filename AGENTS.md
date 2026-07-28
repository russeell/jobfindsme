# Agent Development Rules

1. Read `PROJECT_SPEC.md` and the selected feature before editing code.
2. Implement only one feature at a time and respect its `allowed_paths`.
3. Keep business rules in `src/jobfindsme/core`; adapters may translate input
   and output but must not duplicate those rules.
4. The Core must never import FastAPI, an MCP SDK, or an agent SDK.
5. The deterministic path must work without a model API key.
6. Never send a complete resume to a host model. Pass the local path to the
   Core and return only the minimum confirmed profile summary.
7. Destructive operations require Core-enforced preview and confirm phases.
8. Every completed feature needs automated tests and machine-readable evidence.
9. Do not mark work done when tests are skipped, mocked away, or unverified.
