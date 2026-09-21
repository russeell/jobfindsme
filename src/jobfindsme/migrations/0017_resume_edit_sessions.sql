CREATE TABLE resume_edit_sessions (
    session_id TEXT PRIMARY KEY,
    workspace_id TEXT NOT NULL,
    base_version_id TEXT NOT NULL,
    connection_id TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'active',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY (workspace_id) REFERENCES workspaces(workspace_id) ON DELETE CASCADE,
    FOREIGN KEY (base_version_id) REFERENCES resume_versions(version_id) ON DELETE CASCADE,
    FOREIGN KEY (connection_id) REFERENCES model_connections(connection_id) ON DELETE CASCADE,
    CHECK (status IN ('active', 'saved', 'cancelled'))
);

CREATE TABLE resume_edit_messages (
    message_id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL,
    turn_number INTEGER NOT NULL,
    user_prompt TEXT NOT NULL,
    optional_jd TEXT,
    project_facts_json TEXT NOT NULL,
    redacted_fields_json TEXT NOT NULL,
    created_at TEXT NOT NULL,
    FOREIGN KEY (session_id) REFERENCES resume_edit_sessions(session_id) ON DELETE CASCADE,
    UNIQUE (session_id, turn_number)
);

CREATE TABLE resume_patches (
    patch_id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL,
    turn_number INTEGER NOT NULL,
    section_name TEXT NOT NULL,
    before_json TEXT NOT NULL,
    after_json TEXT NOT NULL,
    rationale TEXT NOT NULL,
    evidence_ids_json TEXT NOT NULL,
    needs_user_input_json TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'proposed',
    created_at TEXT NOT NULL,
    FOREIGN KEY (session_id) REFERENCES resume_edit_sessions(session_id) ON DELETE CASCADE,
    CHECK (status IN ('proposed', 'accepted', 'rejected'))
);

CREATE INDEX idx_resume_edit_sessions_workspace
ON resume_edit_sessions (workspace_id, updated_at);

CREATE INDEX idx_resume_patches_session
ON resume_patches (session_id, turn_number, created_at);
