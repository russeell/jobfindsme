CREATE TABLE job_states (
    workspace_id TEXT NOT NULL,
    job_id TEXT NOT NULL,
    state TEXT NOT NULL,
    note TEXT NOT NULL DEFAULT '',
    updated_at TEXT NOT NULL,
    PRIMARY KEY (workspace_id, job_id),
    FOREIGN KEY (workspace_id, job_id) REFERENCES jobs(workspace_id, job_id)
        ON DELETE CASCADE,
    CHECK (state IN ('discovered', 'saved', 'applied', 'rejected'))
);

CREATE TABLE deletion_tokens (
    token_hash TEXT PRIMARY KEY,
    workspace_id TEXT NOT NULL,
    scope TEXT NOT NULL,
    expires_at TEXT NOT NULL,
    used_at TEXT,
    CHECK (scope IN ('jobs', 'profile', 'workspace'))
);

CREATE TABLE deletion_audit (
    audit_id INTEGER PRIMARY KEY AUTOINCREMENT,
    workspace_hash TEXT NOT NULL,
    scope TEXT NOT NULL,
    deleted_at TEXT NOT NULL
);
