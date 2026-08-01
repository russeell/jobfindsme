ALTER TABLE search_plans
ADD COLUMN salary_policy TEXT NOT NULL DEFAULT 'strict'
CHECK (salary_policy IN ('strict', 'include_undisclosed'));
