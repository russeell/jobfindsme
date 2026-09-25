# Contributing

JobFindsMe currently focuses on the desktop experience: search for real jobs, read the original listing, and research a role with traceable evidence. See the [current status](docs/desktop/HANDOFF.md) and [module map](docs/desktop/STRUCTURE.md) before changing behavior.

Keep changes within one feature, preserve database migrations and user data, and run checks relevant to the change. For desktop UI or browser work, use `npm run build` and the related tests in `apps/desktop/`. For Python changes, run the affected tests under `tests/`; full CI runs across supported hosts. Never claim that an opened website proves automatic job retrieval, and do not submit real applications during testing.

The project is licensed under [MIT](LICENSE). Contributions remain yours; by submitting a contribution for inclusion, you agree to license it under MIT.
