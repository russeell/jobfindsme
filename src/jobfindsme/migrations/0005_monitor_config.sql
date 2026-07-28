CREATE TABLE monitor_configs (
    workspace_id TEXT NOT NULL,
    plan_id TEXT NOT NULL,
    enabled INTEGER NOT NULL DEFAULT 0,
    interval_hours INTEGER NOT NULL DEFAULT 24,
    notification_channel TEXT,
    updated_at TEXT NOT NULL,
    PRIMARY KEY (workspace_id, plan_id),
    FOREIGN KEY (workspace_id) REFERENCES workspaces(workspace_id)
        ON DELETE CASCADE,
    FOREIGN KEY (plan_id) REFERENCES search_plans(plan_id)
        ON DELETE CASCADE,
    CHECK (enabled IN (0, 1)),
    CHECK (interval_hours BETWEEN 1 AND 168)
);
