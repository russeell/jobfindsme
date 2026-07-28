from __future__ import annotations

import json
from datetime import UTC, datetime

from jobfindsme.cli import default_database_path
from jobfindsme.core import JobFindsMeCore
from jobfindsme.monitoring import LocalMonitorRunner
from jobfindsme.notifications import FeishuNotifier


def main() -> None:
    core = JobFindsMeCore(default_database_path())
    notifier = FeishuNotifier.from_env()
    results = LocalMonitorRunner(core.database).run_due(
        now=datetime.now(UTC),
        search=lambda workspace_id, plan_id: core.search_jobs(
            workspace_id=workspace_id,
            plan_id=plan_id,
        ),
        notify=notifier.send if notifier else None,
    )
    print(
        json.dumps(
            [item.model_dump(mode="json") for item in results],
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
