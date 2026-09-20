-- Link an immutable candidate to an immutable human QA approval; no promotion to release.
CREATE TABLE platform.sdm_qa_binding (
 sdm_id uuid PRIMARY KEY REFERENCES platform.sdm_artifact(sdm_id),
 qa_approval_id uuid NOT NULL REFERENCES platform.qa_review_approval(approval_id),
 run_id uuid NOT NULL REFERENCES platform.task_run(run_id),
 created_at timestamptz NOT NULL DEFAULT clock_timestamp()
);
CREATE FUNCTION platform.check_sdm_qa_binding() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
 IF NOT EXISTS (
  SELECT 1 FROM platform.sdm_artifact s JOIN platform.qa_review_approval q ON q.run_id=s.run_id
  WHERE s.sdm_id=NEW.sdm_id AND q.approval_id=NEW.qa_approval_id AND s.run_id=NEW.run_id
   AND s.status='CANDIDATE_NOT_RELEASED'
   AND q.binding->>'specification_checksum'=s.specification_checksum
   AND q.binding->>'task_id'=s.task_id
   AND q.binding->>'project_id'=s.project_id::text
 ) THEN RAISE EXCEPTION 'SDM_QA_BINDING_MISMATCH'; END IF;
 RETURN NEW;
END;
$$;
CREATE TRIGGER sdm_qa_binding_check BEFORE INSERT ON platform.sdm_qa_binding
 FOR EACH ROW EXECUTE FUNCTION platform.check_sdm_qa_binding();
CREATE TRIGGER sdm_qa_binding_immutable BEFORE UPDATE OR DELETE ON platform.sdm_qa_binding
 FOR EACH ROW EXECUTE FUNCTION platform.protect_run_approval();
