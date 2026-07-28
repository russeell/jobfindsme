CREATE TABLE active_context (
    singleton INTEGER PRIMARY KEY CHECK (singleton = 1),
    workspace_id TEXT,
    plan_id TEXT,
    updated_at TEXT NOT NULL
);

CREATE TABLE source_subscriptions (
    subscription_id TEXT PRIMARY KEY,
    workspace_id TEXT NOT NULL,
    plan_id TEXT NOT NULL,
    source_kind TEXT NOT NULL,
    source_name TEXT NOT NULL,
    config_json TEXT NOT NULL,
    enabled INTEGER NOT NULL DEFAULT 1,
    health_status TEXT NOT NULL DEFAULT 'never_checked',
    last_checked_at TEXT,
    last_error TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY (workspace_id) REFERENCES workspaces(workspace_id)
        ON DELETE CASCADE,
    FOREIGN KEY (plan_id) REFERENCES search_plans(plan_id)
        ON DELETE CASCADE,
    UNIQUE (workspace_id, plan_id, source_kind, source_name),
    CHECK (enabled IN (0, 1)),
    CHECK (
        health_status IN ('never_checked', 'healthy', 'degraded', 'failed')
    )
);

CREATE INDEX idx_source_subscriptions_plan
ON source_subscriptions (workspace_id, plan_id, enabled);
