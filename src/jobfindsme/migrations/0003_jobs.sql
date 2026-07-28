CREATE TABLE jobs (
    workspace_id TEXT NOT NULL,
    job_id TEXT NOT NULL,
    fingerprint TEXT NOT NULL,
    content_hash TEXT NOT NULL,
    payload_json TEXT NOT NULL,
    source_name TEXT NOT NULL,
    external_id TEXT NOT NULL,
    liveness TEXT NOT NULL,
    fetched_at TEXT NOT NULL,
    PRIMARY KEY (workspace_id, job_id),
    FOREIGN KEY (workspace_id) REFERENCES workspaces(workspace_id)
        ON DELETE CASCADE,
    UNIQUE (workspace_id, fingerprint)
);

CREATE TABLE job_versions (
    version_id INTEGER PRIMARY KEY AUTOINCREMENT,
    workspace_id TEXT NOT NULL,
    job_id TEXT NOT NULL,
    content_hash TEXT NOT NULL,
    payload_json TEXT NOT NULL,
    observed_at TEXT NOT NULL,
    FOREIGN KEY (workspace_id, job_id) REFERENCES jobs(workspace_id, job_id)
        ON DELETE CASCADE,
    UNIQUE (workspace_id, job_id, content_hash)
);

CREATE INDEX idx_jobs_workspace_liveness
ON jobs (workspace_id, liveness, fetched_at);
