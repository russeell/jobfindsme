CREATE TABLE application_attempts (
    attempt_id TEXT PRIMARY KEY,
    record_id TEXT NOT NULL UNIQUE REFERENCES application_records(record_id),
    workspace_id TEXT NOT NULL,
    job_id TEXT NOT NULL,
    platform_job_id TEXT NOT NULL,
    target_url TEXT NOT NULL,
    title TEXT NOT NULL,
    company TEXT NOT NULL,
    file_name TEXT,
    file_sha256 TEXT,
    state TEXT NOT NULL CHECK(state IN ('running','completed','blocked','failed','cancelled','uncertain')),
    phase TEXT NOT NULL DEFAULT 'reserved',
    write_started INTEGER NOT NULL DEFAULT 0,
    message_confirmed INTEGER NOT NULL DEFAULT 0,
    resume_confirmed INTEGER NOT NULL DEFAULT 0,
    detail TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY(workspace_id,job_id) REFERENCES jobs(workspace_id,job_id)
);
CREATE INDEX application_attempts_target ON application_attempts(platform_job_id,created_at);
