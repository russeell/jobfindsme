-- Keep historical foreign keys intact when a model configuration is removed.
ALTER TABLE model_connections ADD COLUMN deleted_at TEXT;
