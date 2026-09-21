CREATE TABLE job_tracking_flags (
    workspace_id TEXT NOT NULL,
    job_id TEXT NOT NULL,
    saved INTEGER NOT NULL DEFAULT 0,
    applied INTEGER NOT NULL DEFAULT 0,
    updated_at TEXT NOT NULL,
    PRIMARY KEY (workspace_id, job_id),
    FOREIGN KEY (workspace_id, job_id) REFERENCES jobs(workspace_id, job_id) ON DELETE CASCADE,
    CHECK (saved IN (0, 1)),
    CHECK (applied IN (0, 1))
);

CREATE TABLE job_tracking_events (
    event_id TEXT PRIMARY KEY,
    workspace_id TEXT NOT NULL,
    job_id TEXT NOT NULL,
    event_type TEXT NOT NULL,
    enabled INTEGER NOT NULL,
    created_at TEXT NOT NULL,
    FOREIGN KEY (workspace_id, job_id) REFERENCES jobs(workspace_id, job_id) ON DELETE CASCADE,
    CHECK (event_type IN ('saved', 'applied', 'apply_opened')),
    CHECK (enabled IN (0, 1))
);

CREATE INDEX idx_job_tracking_events_job
ON job_tracking_events (workspace_id, job_id, created_at, event_id);

INSERT INTO job_tracking_flags (workspace_id, job_id, saved, applied, updated_at)
SELECT workspace_id, job_id,
       CASE WHEN state = 'saved' THEN 1 ELSE 0 END,
       CASE WHEN state = 'applied' THEN 1 ELSE 0 END,
       updated_at
FROM job_states
WHERE state IN ('saved', 'applied')
ON CONFLICT(workspace_id, job_id) DO UPDATE SET
    saved = MAX(job_tracking_flags.saved, excluded.saved),
    applied = MAX(job_tracking_flags.applied, excluded.applied),
    updated_at = MAX(job_tracking_flags.updated_at, excluded.updated_at);
