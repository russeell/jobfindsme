ALTER TABLE scoring_rule_versions ADD COLUMN config_json TEXT;
CREATE TABLE active_matching_rules (
 workspace_id TEXT PRIMARY KEY REFERENCES workspaces(workspace_id) ON DELETE CASCADE,
 rule_version_id TEXT NOT NULL REFERENCES scoring_rule_versions(rule_version_id)
);
ALTER TABLE desktop_search_runs ADD COLUMN rerank_json TEXT;
