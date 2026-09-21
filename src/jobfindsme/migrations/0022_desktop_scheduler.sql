CREATE TABLE desktop_scheduled_tasks (
    task_id TEXT PRIMARY KEY,
    workspace_id TEXT NOT NULL,
    name TEXT NOT NULL,
    intent TEXT NOT NULL,
    source_ids_json TEXT NOT NULL,
    filter_snapshot_json TEXT NOT NULL,
    resume_version_id TEXT NOT NULL,
    rule_version_id TEXT NOT NULL,
    frequency TEXT NOT NULL,
    local_time TEXT,
    weekday INTEGER,
    interval_minutes INTEGER,
    timezone TEXT NOT NULL,
    catch_up_policy TEXT NOT NULL DEFAULT 'once',
    status TEXT NOT NULL,
    next_run_at TEXT NOT NULL,
    last_error TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY (workspace_id) REFERENCES workspaces(workspace_id) ON DELETE CASCADE,
    FOREIGN KEY (resume_version_id) REFERENCES resume_versions(version_id),
    FOREIGN KEY (rule_version_id) REFERENCES scoring_rule_versions(rule_version_id),
    CHECK (frequency IN ('interval', 'daily', 'weekly')),
    CHECK (catch_up_policy IN ('once', 'skip')),
    CHECK (status IN ('active', 'paused')),
    CHECK (weekday IS NULL OR weekday BETWEEN 0 AND 6),
    CHECK (interval_minutes IS NULL OR interval_minutes BETWEEN 15 AND 10080)
);

CREATE TABLE desktop_task_runs (
    run_id TEXT PRIMARY KEY,
    task_id TEXT NOT NULL,
    scheduled_for TEXT NOT NULL,
    status TEXT NOT NULL,
    started_at TEXT NOT NULL,
    finished_at TEXT,
    search_run_id TEXT,
    new_count INTEGER NOT NULL DEFAULT 0,
    changed_count INTEGER NOT NULL DEFAULT 0,
    source_failures_json TEXT NOT NULL DEFAULT '[]',
    result_snapshot_json TEXT NOT NULL DEFAULT '{}',
    result_fingerprint TEXT,
    error TEXT,
    FOREIGN KEY (task_id) REFERENCES desktop_scheduled_tasks(task_id) ON DELETE CASCADE,
    UNIQUE (task_id, scheduled_for),
    CHECK (status IN ('running', 'success', 'partial', 'failed', 'login_required'))
);

CREATE TABLE desktop_task_notifications (
    notification_id TEXT PRIMARY KEY,
    task_id TEXT NOT NULL,
    run_id TEXT NOT NULL,
    event_key TEXT NOT NULL,
    kind TEXT NOT NULL,
    title TEXT NOT NULL,
    body TEXT NOT NULL,
    created_at TEXT NOT NULL,
    delivered_at TEXT,
    FOREIGN KEY (task_id) REFERENCES desktop_scheduled_tasks(task_id) ON DELETE CASCADE,
    FOREIGN KEY (run_id) REFERENCES desktop_task_runs(run_id) ON DELETE CASCADE,
    UNIQUE (task_id, event_key),
    CHECK (kind IN ('new_jobs', 'changed_jobs', 'failure'))
);

CREATE INDEX idx_desktop_scheduled_tasks_due
ON desktop_scheduled_tasks (status, next_run_at);

CREATE INDEX idx_desktop_task_runs_task
ON desktop_task_runs (task_id, scheduled_for);
