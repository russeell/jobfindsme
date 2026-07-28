CREATE TABLE monitor_runs (
    workspace_id TEXT NOT NULL,
    plan_id TEXT NOT NULL,
    scheduled_for TEXT NOT NULL,
    status TEXT NOT NULL,
    attempt INTEGER NOT NULL DEFAULT 1,
    started_at TEXT NOT NULL,
    finished_at TEXT,
    matched_count INTEGER,
    new_count INTEGER,
    error TEXT,
    PRIMARY KEY (workspace_id, plan_id, scheduled_for),
    FOREIGN KEY (workspace_id, plan_id)
        REFERENCES monitor_configs(workspace_id, plan_id)
        ON DELETE CASCADE,
    CHECK (status IN ('running', 'success', 'failed'))
);

CREATE TABLE monitor_seen_jobs (
    workspace_id TEXT NOT NULL,
    plan_id TEXT NOT NULL,
    job_id TEXT NOT NULL,
    first_seen_at TEXT NOT NULL,
    PRIMARY KEY (workspace_id, plan_id, job_id),
    FOREIGN KEY (workspace_id, plan_id)
        REFERENCES monitor_configs(workspace_id, plan_id)
        ON DELETE CASCADE
);
