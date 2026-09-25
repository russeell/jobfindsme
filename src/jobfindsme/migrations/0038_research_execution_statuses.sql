CREATE TABLE research_executions_next (
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
    context_json TEXT NOT NULL DEFAULT '{}',
    FOREIGN KEY (workspace_id) REFERENCES workspaces(workspace_id) ON DELETE CASCADE,
    FOREIGN KEY (report_id) REFERENCES research_reports(report_id),
    CHECK (status IN ('running', 'complete', 'failed', 'cancelled',
                     'no_results', 'search_service_error', 'read_failed',
                     'entity_mismatch', 'unsupported_claim'))
);
INSERT INTO research_executions_next
    (execution_id, workspace_id, conversation_id, subject_key, status,
     budgets_json, actions_json, evidence_json, failures_json, report_id,
     started_at, updated_at, context_json)
SELECT execution_id, workspace_id, conversation_id, subject_key, status,
       budgets_json, actions_json, evidence_json, failures_json, report_id,
       started_at, updated_at, context_json
FROM research_executions;
DROP TABLE research_executions;
ALTER TABLE research_executions_next RENAME TO research_executions;
CREATE INDEX idx_research_executions_workspace
ON research_executions(workspace_id, subject_key, updated_at);
