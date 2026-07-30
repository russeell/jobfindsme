CREATE TABLE search_job_impressions (
    workspace_id TEXT NOT NULL,
    plan_id TEXT NOT NULL,
    job_id TEXT NOT NULL,
    first_shown_at TEXT NOT NULL,
    last_shown_at TEXT NOT NULL,
    shown_count INTEGER NOT NULL DEFAULT 1,
    last_content_hash TEXT NOT NULL,
    last_liveness TEXT NOT NULL,
    PRIMARY KEY (workspace_id, plan_id, job_id),
    FOREIGN KEY (workspace_id) REFERENCES workspaces(workspace_id)
        ON DELETE CASCADE,
    FOREIGN KEY (plan_id) REFERENCES search_plans(plan_id)
        ON DELETE CASCADE,
    FOREIGN KEY (workspace_id, job_id) REFERENCES jobs(workspace_id, job_id)
        ON DELETE CASCADE,
    CHECK (shown_count >= 1)
);

CREATE INDEX idx_search_job_impressions_plan
ON search_job_impressions (workspace_id, plan_id, last_shown_at);
