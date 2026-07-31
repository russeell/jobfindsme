-- v0.5.0: monitors may use an arbitrary cron schedule (time + frequency)
ALTER TABLE monitor_configs ADD COLUMN schedule_cron TEXT;
