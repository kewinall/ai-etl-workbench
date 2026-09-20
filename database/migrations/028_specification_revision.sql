ALTER TABLE platform.specification
 ADD COLUMN run_id uuid REFERENCES platform.task_run(run_id),
 ADD COLUMN content_checksum text,
 ADD COLUMN naming_contract_id uuid REFERENCES platform.naming_contract(contract_id);
ALTER TABLE platform.specification ADD CONSTRAINT specification_run_binding CHECK (
 (run_id IS NULL AND content_checksum IS NULL AND naming_contract_id IS NULL) OR
 (run_id IS NOT NULL AND content_checksum IS NOT NULL AND content_checksum ~ '^[a-f0-9]{64}$' AND naming_contract_id IS NOT NULL)
);
CREATE TABLE platform.specification_approval (
 approval_id uuid PRIMARY KEY,
 specification_id uuid NOT NULL UNIQUE REFERENCES platform.specification(specification_id),
 operator_id uuid NOT NULL REFERENCES platform.operator_profile(operator_id),
 content_checksum text NOT NULL CHECK(content_checksum ~ '^[a-f0-9]{64}$'),
 created_at timestamptz NOT NULL DEFAULT now()
);
CREATE TRIGGER specification_approval_immutable BEFORE UPDATE ON platform.specification_approval
 FOR EACH ROW EXECUTE FUNCTION platform.protect_run_approval();
CREATE FUNCTION platform.protect_versioned_specification() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
 IF OLD.run_id IS NOT NULL AND (to_jsonb(NEW)-'is_current') IS DISTINCT FROM (to_jsonb(OLD)-'is_current') THEN
  RAISE EXCEPTION 'Versioned specification is immutable';
 END IF;
 RETURN NEW;
END;
$$;
CREATE TRIGGER versioned_specification_immutable BEFORE UPDATE ON platform.specification
 FOR EACH ROW EXECUTE FUNCTION platform.protect_versioned_specification();
