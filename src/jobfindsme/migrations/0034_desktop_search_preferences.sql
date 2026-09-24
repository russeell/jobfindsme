CREATE TABLE desktop_search_preferences (
    workspace_id TEXT PRIMARY KEY REFERENCES workspaces(workspace_id) ON DELETE CASCADE,
    target_role TEXT NOT NULL DEFAULT '',
    cities_json TEXT NOT NULL DEFAULT '[]',
    salary_min_k INTEGER,
    salary_max_k INTEGER,
    updated_at TEXT NOT NULL,
    CHECK (salary_min_k IS NULL OR salary_min_k BETWEEN 0 AND 1000),
    CHECK (salary_max_k IS NULL OR salary_max_k BETWEEN 0 AND 1000),
    CHECK (salary_min_k IS NULL OR salary_max_k IS NULL OR salary_min_k <= salary_max_k)
);
