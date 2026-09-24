ALTER TABLE model_connections ADD COLUMN auth_mode TEXT NOT NULL DEFAULT 'api_key' CHECK (auth_mode IN ('api_key', 'none'));
