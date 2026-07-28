# Local Scheduling

Run one idempotent monitoring cycle:

```bash
python3 -m jobfindsme.monitoring
```

Use the operating system scheduler of your choice. The command only runs plans
that were explicitly enabled through `configure_monitor`.

For Feishu notifications, provide `FEISHU_WEBHOOK_URL` and `FEISHU_SECRET` in a
user-owned environment file with mode `600`. Removing either value revokes
notifications. Do not place either secret in this repository or SQLite.

The scheduler should run more frequently than the shortest configured plan
interval. Duplicate invocations are safe; each plan and time slot is claimed
once, and stale or failed runs can be retried.
