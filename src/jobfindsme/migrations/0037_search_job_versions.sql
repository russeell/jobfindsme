ALTER TABLE desktop_search_runs ADD COLUMN job_snapshot_refs_json TEXT NOT NULL DEFAULT '{}';
ALTER TABLE research_executions ADD COLUMN context_json TEXT NOT NULL DEFAULT '{}';
