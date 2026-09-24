CREATE TABLE active_resume_imports (
    workspace_id TEXT PRIMARY KEY,
    profile_id TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY (workspace_id) REFERENCES workspaces(workspace_id)
        ON DELETE CASCADE,
    FOREIGN KEY (profile_id) REFERENCES candidate_profiles(profile_id)
        ON DELETE CASCADE
);

CREATE TABLE model_test_runs (
    test_id TEXT PRIMARY KEY,
    connection_id TEXT NOT NULL,
    status TEXT NOT NULL,
    started_at TEXT NOT NULL,
    finished_at TEXT,
    FOREIGN KEY (connection_id) REFERENCES model_connections(connection_id)
        ON DELETE CASCADE,
    CHECK (status IN ('testing', 'verified', 'failed', 'cancelled'))
);

ALTER TABLE model_connections ADD COLUMN credential_ref TEXT;

CREATE INDEX idx_model_test_runs_connection
ON model_test_runs (connection_id, started_at);
