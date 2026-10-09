CREATE TABLE application_records (
    record_id TEXT PRIMARY KEY,
    workspace_id TEXT NOT NULL,
    job_id TEXT NOT NULL,
    resume_version_id TEXT REFERENCES resume_versions(version_id),
    message TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL CHECK(status IN ('prepared','opened','contacted','resume_sent','uncertain')),
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY(workspace_id,job_id) REFERENCES jobs(workspace_id,job_id)
);
CREATE INDEX application_records_job ON application_records(workspace_id,job_id,created_at);
