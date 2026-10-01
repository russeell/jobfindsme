CREATE TABLE job_preparations (
    workspace_id TEXT NOT NULL,
    job_id TEXT NOT NULL,
    stage TEXT NOT NULL DEFAULT 'considering'
        CHECK(stage IN ('considering','applied','interview','offer','closed')),
    next_action TEXT NOT NULL DEFAULT '',
    due_date TEXT,
    note TEXT NOT NULL DEFAULT '',
    resume_version_id TEXT REFERENCES resume_versions(version_id) ON DELETE SET NULL,
    updated_at TEXT NOT NULL,
    PRIMARY KEY(workspace_id, job_id),
    FOREIGN KEY(workspace_id, job_id) REFERENCES jobs(workspace_id, job_id)
);
ALTER TABLE resume_edit_sessions ADD COLUMN target_job_id TEXT;
