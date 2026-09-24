CREATE TABLE resume_versions (
    version_id TEXT PRIMARY KEY,
    workspace_id TEXT NOT NULL,
    profile_id TEXT NOT NULL,
    source_document_id TEXT NOT NULL,
    parent_version_id TEXT,
    version_number INTEGER NOT NULL,
    content_json TEXT NOT NULL,
    is_current INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL,
    FOREIGN KEY (workspace_id) REFERENCES workspaces(workspace_id)
        ON DELETE CASCADE,
    FOREIGN KEY (profile_id) REFERENCES candidate_profiles(profile_id)
        ON DELETE CASCADE,
    FOREIGN KEY (source_document_id) REFERENCES source_documents(document_id)
        ON DELETE RESTRICT,
    FOREIGN KEY (parent_version_id) REFERENCES resume_versions(version_id)
        ON DELETE SET NULL,
    UNIQUE (workspace_id, version_number),
    CHECK (version_number > 0),
    CHECK (is_current IN (0, 1))
);

CREATE UNIQUE INDEX idx_resume_versions_current
ON resume_versions (workspace_id)
WHERE is_current = 1;

CREATE INDEX idx_resume_versions_profile
ON resume_versions (workspace_id, profile_id, version_number);
