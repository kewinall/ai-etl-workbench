-- Permanent platform ownership. Deliberately conservative across connections:
-- the same schema/table name cannot be assigned to another Run via an alias.
CREATE TABLE platform.task_run_target_claim (
 run_id uuid PRIMARY KEY REFERENCES platform.task_run(run_id),
 project_id uuid NOT NULL REFERENCES platform.project(project_id),
 task_id text NOT NULL REFERENCES platform.task(task_id),
 schema_name text NOT NULL CHECK(schema_name='ai_sample'),
 table_name text NOT NULL CHECK(table_name ~ '^[a-z][a-z0-9_]{0,62}$'),
 settings_checksum text NOT NULL CHECK(settings_checksum ~ '^[a-f0-9]{64}$'),
 specification_checksum text NOT NULL CHECK(specification_checksum ~ '^[a-f0-9]{64}$'),
 hpl_checksum text NOT NULL CHECK(hpl_checksum ~ '^[a-f0-9]{64}$'),
 ddl_checksum text NOT NULL CHECK(ddl_checksum ~ '^[a-f0-9]{64}$'),
 registry_created_at timestamptz NOT NULL,
 registry_rebuilt_at timestamptz NOT NULL,
 created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
 UNIQUE(schema_name,table_name)
);
CREATE TRIGGER target_claim_immutable BEFORE UPDATE OR DELETE ON platform.task_run_target_claim
 FOR EACH ROW EXECUTE FUNCTION platform.protect_run_approval();
CREATE FUNCTION platform.check_target_claim_before_write() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
 PERFORM 1 FROM platform.task_run WHERE run_id=NEW.run_id AND task_id=NEW.task_id
  AND project_id=NEW.project_id AND state='NEEDS_REVIEW' AND NOT write_started FOR SHARE;
 IF NOT FOUND THEN RAISE EXCEPTION 'Target must be claimed before execution'; END IF;
 RETURN NEW;
END;
$$;
CREATE TRIGGER target_claim_prewrite BEFORE INSERT ON platform.task_run_target_claim
 FOR EACH ROW EXECUTE FUNCTION platform.check_target_claim_before_write();
