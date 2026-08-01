# Contributing

## Skill taxonomy

Skills and aliases live in `src/jobfindsme/resources/taxonomy/skills.json`.

1. Add a canonical skill and its real-world aliases.
2. Do not reuse an alias owned by another skill.
3. Run `python -m scripts.validate_taxonomy` and `python -m pytest tests/test_taxonomy.py`.
4. Include one realistic resume or job-description example in the pull request.

The default matcher remains deterministic and requires no model API. Semantic
matching can be added later as an optional, separately evaluated provider.
