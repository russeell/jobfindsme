CREATE TABLE research_conversations (
    conversation_id TEXT PRIMARY KEY,
    workspace_id TEXT NOT NULL,
    subject_key TEXT NOT NULL DEFAULT '',
    context_json TEXT NOT NULL DEFAULT '{}',
    turns_json TEXT NOT NULL DEFAULT '[]',
    report_ids_json TEXT NOT NULL DEFAULT '[]',
    draft TEXT,
    pending_json TEXT,
    updated_at TEXT NOT NULL,
    hidden_at TEXT,
    FOREIGN KEY (workspace_id) REFERENCES workspaces(workspace_id) ON DELETE CASCADE
);
CREATE INDEX idx_research_conversations_workspace
ON research_conversations(workspace_id, updated_at);

CREATE TABLE research_executions (
    execution_id TEXT PRIMARY KEY,
    workspace_id TEXT NOT NULL,
    conversation_id TEXT,
    subject_key TEXT NOT NULL,
    status TEXT NOT NULL,
    budgets_json TEXT NOT NULL DEFAULT '{}',
    actions_json TEXT NOT NULL DEFAULT '[]',
    evidence_json TEXT NOT NULL DEFAULT '[]',
    failures_json TEXT NOT NULL DEFAULT '[]',
    report_id TEXT,
    started_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY (workspace_id) REFERENCES workspaces(workspace_id) ON DELETE CASCADE,
    FOREIGN KEY (report_id) REFERENCES research_reports(report_id),
    CHECK (status IN ('running', 'complete', 'failed', 'cancelled'))
);
CREATE INDEX idx_research_executions_workspace
ON research_executions(workspace_id, subject_key, updated_at);
