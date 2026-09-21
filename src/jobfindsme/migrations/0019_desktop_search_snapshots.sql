CREATE TABLE scoring_rule_versions (
    rule_version_id TEXT PRIMARY KEY,
    workspace_id TEXT NOT NULL,
    name TEXT NOT NULL,
    weights_json TEXT NOT NULL,
    created_at TEXT NOT NULL,
    FOREIGN KEY (workspace_id) REFERENCES workspaces(workspace_id) ON DELETE CASCADE
);

CREATE TABLE desktop_search_runs (
    run_id TEXT PRIMARY KEY,
    workspace_id TEXT NOT NULL,
    resume_version_id TEXT,
    rule_version_id TEXT NOT NULL,
    intent TEXT NOT NULL,
    filter_snapshot_json TEXT NOT NULL,
    ordered_job_ids_json TEXT NOT NULL,
    scores_json TEXT NOT NULL,
    created_at TEXT NOT NULL,
    FOREIGN KEY (workspace_id) REFERENCES workspaces(workspace_id) ON DELETE CASCADE,
    FOREIGN KEY (resume_version_id) REFERENCES resume_versions(version_id),
    FOREIGN KEY (rule_version_id) REFERENCES scoring_rule_versions(rule_version_id)
);

CREATE INDEX idx_desktop_search_runs_workspace
ON desktop_search_runs (workspace_id, created_at);

CREATE TABLE job_read_events (
    event_id TEXT PRIMARY KEY,
    workspace_id TEXT NOT NULL,
    job_id TEXT NOT NULL,
    event_type TEXT NOT NULL,
    created_at TEXT NOT NULL,
    FOREIGN KEY (workspace_id, job_id) REFERENCES jobs(workspace_id, job_id) ON DELETE CASCADE,
    CHECK (event_type IN ('read', 'unread'))
);

CREATE INDEX idx_job_read_events_job
ON job_read_events (workspace_id, job_id, created_at, event_id);
