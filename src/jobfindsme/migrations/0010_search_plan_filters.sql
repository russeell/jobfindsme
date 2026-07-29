-- Add optional filter columns. NULL = unfiltered.

ALTER TABLE search_plans ADD COLUMN recruitment_track TEXT;
ALTER TABLE search_plans ADD COLUMN employment_type TEXT;
