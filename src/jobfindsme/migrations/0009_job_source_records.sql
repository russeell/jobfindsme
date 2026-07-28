CREATE TABLE job_source_records (
    record_id TEXT PRIMARY KEY,
    workspace_id TEXT NOT NULL,
    job_id TEXT NOT NULL,
    source_name TEXT NOT NULL,
    external_id TEXT NOT NULL,
    source_url TEXT NOT NULL,
    apply_url TEXT NOT NULL,
    liveness TEXT NOT NULL,
    observed_at TEXT NOT NULL,
    FOREIGN KEY (workspace_id, job_id) REFERENCES jobs(workspace_id, job_id)
        ON DELETE CASCADE,
    UNIQUE (workspace_id, source_name, external_id),
    CHECK (liveness IN ('active', 'stale', 'closed', 'unknown'))
);

CREATE INDEX idx_job_source_records_job
ON job_source_records (workspace_id, job_id);
