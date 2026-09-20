-- Extend existing SDM metadata. Legacy paths/checksums are not rewritten.
ALTER TABLE platform.sdm_artifact
 ADD COLUMN project_id uuid REFERENCES platform.project(project_id),
 ADD COLUMN run_id uuid REFERENCES platform.task_run(run_id) ON DELETE CASCADE,
 ADD COLUMN specification_id uuid REFERENCES platform.specification(specification_id) ON DELETE CASCADE,
 ADD COLUMN specification_approval_id uuid REFERENCES platform.specification_approval(approval_id),
 ADD COLUMN naming_contract_id uuid REFERENCES platform.naming_contract(contract_id),
 ADD COLUMN specification_checksum text,
 ADD COLUMN naming_checksum text,
 ADD COLUMN file_size bigint,
 ADD COLUMN renderer_version text,
 ADD COLUMN status text NOT NULL DEFAULT 'LEGACY_UNVERIFIED',
 ADD CONSTRAINT sdm_status CHECK(status IN ('LEGACY_UNVERIFIED','CANDIDATE_NOT_RELEASED')),
 ADD CONSTRAINT sdm_bound_fields CHECK(status='LEGACY_UNVERIFIED' OR (
   project_id IS NOT NULL AND run_id IS NOT NULL AND specification_id IS NOT NULL
   AND specification_approval_id IS NOT NULL AND naming_contract_id IS NOT NULL
   AND specification_checksum IS NOT NULL AND specification_checksum ~ '^[a-f0-9]{64}$'
   AND naming_checksum IS NOT NULL AND naming_checksum ~ '^[a-f0-9]{64}$'
   AND checksum ~ '^[a-f0-9]{64}$' AND file_size IS NOT NULL AND file_size BETWEEN 1 AND 16777216
   AND renderer_version IS NOT NULL AND renderer_version='openpyxl-sdm-v1'));

CREATE UNIQUE INDEX sdm_bound_content_unique ON platform.sdm_artifact
 (run_id,specification_id,specification_approval_id,naming_contract_id,renderer_version,checksum)
 WHERE status='CANDIDATE_NOT_RELEASED';

CREATE FUNCTION platform.check_sdm_binding() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
 IF NEW.status='CANDIDATE_NOT_RELEASED' AND NOT EXISTS (
  SELECT 1 FROM platform.task t
  JOIN platform.task_run r ON r.task_id=t.task_id
  JOIN platform.specification s ON s.task_id=t.task_id AND s.run_id=r.run_id
  JOIN platform.specification_approval a ON a.specification_id=s.specification_id
  JOIN platform.naming_contract n ON n.task_id=t.task_id
  WHERE t.task_id=NEW.task_id AND t.project_id=NEW.project_id
   AND r.run_id=NEW.run_id AND s.specification_id=NEW.specification_id
   AND a.approval_id=NEW.specification_approval_id AND n.contract_id=NEW.naming_contract_id
   AND s.content_checksum=NEW.specification_checksum AND a.content_checksum=s.content_checksum
   AND n.checksum=NEW.naming_checksum
   AND s.spec_json->'naming'->>'contract_id'=n.contract_id::text
   AND s.spec_json->'naming'->>'checksum'=n.checksum
 ) THEN
  RAISE EXCEPTION 'SDM_VERSION_BINDING_MISMATCH';
 END IF;
 RETURN NEW;
END;
$$;
CREATE TRIGGER sdm_binding_check BEFORE INSERT ON platform.sdm_artifact
 FOR EACH ROW EXECUTE FUNCTION platform.check_sdm_binding();
CREATE TRIGGER sdm_artifact_immutable BEFORE UPDATE ON platform.sdm_artifact
 FOR EACH ROW EXECUTE FUNCTION platform.protect_run_approval();
