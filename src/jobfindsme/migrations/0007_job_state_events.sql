CREATE TABLE job_state_events (
    event_id TEXT PRIMARY KEY,
    workspace_id TEXT NOT NULL,
    job_id TEXT NOT NULL,
    previous_state TEXT,
    new_state TEXT NOT NULL,
    note TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL,
    FOREIGN KEY (workspace_id, job_id) REFERENCES jobs(workspace_id, job_id)
        ON DELETE CASCADE,
    CHECK (
        previous_state IS NULL
        OR previous_state IN ('discovered', 'saved', 'applied', 'rejected')
    ),
    CHECK (new_state IN ('discovered', 'saved', 'applied', 'rejected'))
);

CREATE INDEX idx_job_state_events_job
ON job_state_events (workspace_id, job_id, created_at);
