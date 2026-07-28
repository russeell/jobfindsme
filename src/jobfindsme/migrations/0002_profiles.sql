CREATE TABLE source_documents (
    document_id TEXT PRIMARY KEY,
    workspace_id TEXT NOT NULL,
    file_name TEXT NOT NULL,
    media_type TEXT NOT NULL,
    content_hash TEXT NOT NULL,
    import_mode TEXT NOT NULL,
    source_path TEXT,
    managed_path TEXT,
    parser_version TEXT NOT NULL,
    created_at TEXT NOT NULL,
    FOREIGN KEY (workspace_id) REFERENCES workspaces(workspace_id)
        ON DELETE CASCADE,
    UNIQUE (workspace_id, content_hash, parser_version),
    CHECK (import_mode IN ('reference', 'managed', 'forget-source')),
    CHECK (
        (import_mode = 'reference' AND source_path IS NOT NULL
            AND managed_path IS NULL)
        OR
        (import_mode = 'managed' AND source_path IS NULL
            AND managed_path IS NOT NULL)
        OR
        (import_mode = 'forget-source' AND source_path IS NULL
            AND managed_path IS NULL)
    )
);

CREATE TABLE candidate_profiles (
    profile_id TEXT PRIMARY KEY,
    workspace_id TEXT NOT NULL,
    document_id TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'draft',
    parser_version TEXT NOT NULL,
    created_at TEXT NOT NULL,
    confirmed_at TEXT,
    FOREIGN KEY (workspace_id) REFERENCES workspaces(workspace_id)
        ON DELETE CASCADE,
    FOREIGN KEY (document_id) REFERENCES source_documents(document_id)
        ON DELETE CASCADE,
    UNIQUE (workspace_id, document_id, parser_version),
    CHECK (status IN ('draft', 'confirmed'))
);

CREATE TABLE profile_facts (
    fact_id TEXT PRIMARY KEY,
    profile_id TEXT NOT NULL,
    workspace_id TEXT NOT NULL,
    fact_type TEXT NOT NULL,
    original_value TEXT NOT NULL,
    current_value TEXT NOT NULL,
    evidence_snippet TEXT NOT NULL,
    evidence_start INTEGER NOT NULL,
    evidence_end INTEGER NOT NULL,
    status TEXT NOT NULL DEFAULT 'proposed',
    FOREIGN KEY (profile_id) REFERENCES candidate_profiles(profile_id)
        ON DELETE CASCADE,
    FOREIGN KEY (workspace_id) REFERENCES workspaces(workspace_id)
        ON DELETE CASCADE,
    CHECK (status IN ('proposed', 'confirmed', 'rejected')),
    CHECK (evidence_start >= 0),
    CHECK (evidence_end > evidence_start),
    CHECK (length(evidence_snippet) <= 500)
);

CREATE INDEX idx_profiles_workspace
ON candidate_profiles (workspace_id, created_at);

CREATE INDEX idx_profile_facts_profile
ON profile_facts (profile_id, status);
