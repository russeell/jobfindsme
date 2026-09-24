CREATE TABLE research_reports (
    report_id TEXT PRIMARY KEY,
    workspace_id TEXT NOT NULL,
    job_id TEXT NOT NULL,
    resume_version_id TEXT NOT NULL,
    status TEXT NOT NULL,
    jd_facts_json TEXT NOT NULL,
    resume_observations_json TEXT NOT NULL,
    project_rewrites_json TEXT NOT NULL,
    interview_topics_json TEXT NOT NULL,
    model_connection_id TEXT,
    model_status TEXT NOT NULL DEFAULT 'not_requested',
    limitations_json TEXT NOT NULL,
    created_at TEXT NOT NULL,
    FOREIGN KEY (workspace_id, job_id) REFERENCES jobs(workspace_id, job_id) ON DELETE CASCADE,
    FOREIGN KEY (resume_version_id) REFERENCES resume_versions(version_id),
    FOREIGN KEY (model_connection_id) REFERENCES model_connections(connection_id),
    CHECK (status IN ('complete', 'limited')),
    CHECK (model_status IN ('not_requested', 'complete', 'failed', 'cancelled'))
);

CREATE TABLE research_evidence (
    evidence_id TEXT PRIMARY KEY,
    report_id TEXT NOT NULL,
    url TEXT,
    platform TEXT NOT NULL,
    published_at TEXT,
    retrieved_at TEXT NOT NULL,
    company TEXT NOT NULL,
    team TEXT,
    excerpt TEXT NOT NULL,
    evidence_kind TEXT NOT NULL,
    verification_status TEXT NOT NULL,
    relevance TEXT NOT NULL,
    limitations TEXT NOT NULL,
    FOREIGN KEY (report_id) REFERENCES research_reports(report_id) ON DELETE CASCADE,
    CHECK (evidence_kind IN ('public_source', 'user_excerpt')),
    CHECK (verification_status IN ('independently_retrieved', 'user_supplied_unverified')),
    CHECK (relevance IN ('company', 'team', 'role'))
);

CREATE INDEX idx_research_reports_job
ON research_reports (workspace_id, job_id, created_at);

CREATE INDEX idx_research_evidence_report
ON research_evidence (report_id, retrieved_at);
