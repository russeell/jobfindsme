CREATE TABLE workspaces (
    workspace_id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE search_plans (
    plan_id TEXT PRIMARY KEY,
    workspace_id TEXT NOT NULL,
    name TEXT NOT NULL,
    target_roles_json TEXT NOT NULL,
    locations_json TEXT NOT NULL,
    salary_min_k INTEGER,
    salary_max_k INTEGER,
    experience_min_years INTEGER,
    experience_max_years INTEGER,
    official_sources_only INTEGER NOT NULL DEFAULT 1,
    exclusions_json TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY (workspace_id) REFERENCES workspaces(workspace_id)
        ON DELETE CASCADE,
    UNIQUE (workspace_id, name),
    CHECK (salary_min_k IS NULL OR salary_min_k >= 0),
    CHECK (salary_max_k IS NULL OR salary_max_k >= 0),
    CHECK (
        salary_min_k IS NULL
        OR salary_max_k IS NULL
        OR salary_min_k <= salary_max_k
    ),
    CHECK (experience_min_years IS NULL OR experience_min_years >= 0),
    CHECK (experience_max_years IS NULL OR experience_max_years >= 0),
    CHECK (
        experience_min_years IS NULL
        OR experience_max_years IS NULL
        OR experience_min_years <= experience_max_years
    )
);

CREATE INDEX idx_search_plans_workspace
ON search_plans (workspace_id, created_at);
