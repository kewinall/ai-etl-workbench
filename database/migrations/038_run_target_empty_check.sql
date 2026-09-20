CREATE TABLE platform.task_run_target_empty_check (
 run_id uuid PRIMARY KEY REFERENCES platform.task_run_target_claim(run_id),
 task_id text NOT NULL REFERENCES platform.task(task_id),
 project_id uuid NOT NULL REFERENCES platform.project(project_id),
 settings_checksum text NOT NULL CHECK(settings_checksum ~ '^[a-f0-9]{64}$'),
 hpl_checksum text NOT NULL CHECK(hpl_checksum ~ '^[a-f0-9]{64}$'),
 sql_checksum text NOT NULL CHECK(sql_checksum ~ '^[a-f0-9]{64}$'),
 created_at timestamptz NOT NULL DEFAULT clock_timestamp()
);
CREATE TRIGGER target_empty_check_prewrite BEFORE INSERT ON platform.task_run_target_empty_check
 FOR EACH ROW EXECUTE FUNCTION platform.check_target_claim_before_write();
CREATE TRIGGER target_empty_check_immutable BEFORE UPDATE OR DELETE ON platform.task_run_target_empty_check
 FOR EACH ROW EXECUTE FUNCTION platform.protect_run_approval();
