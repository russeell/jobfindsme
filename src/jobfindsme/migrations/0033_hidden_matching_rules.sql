ALTER TABLE scoring_rule_versions ADD COLUMN hidden_at TEXT;
CREATE INDEX idx_scoring_rule_versions_visible
ON scoring_rule_versions (workspace_id, created_at)
WHERE hidden_at IS NULL;
