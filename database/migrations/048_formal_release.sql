CREATE TABLE platform.release_candidate_record (
 candidate_id uuid PRIMARY KEY,
 run_id uuid NOT NULL REFERENCES platform.task_run(run_id),
 task_id text NOT NULL REFERENCES platform.task(task_id),
 project_id uuid NOT NULL REFERENCES platform.project(project_id),
 sdm_id uuid NOT NULL REFERENCES platform.sdm_artifact(sdm_id),
 qa_binding_checksum text NOT NULL CHECK(qa_binding_checksum ~ '^[a-f0-9]{64}$'),
 checksum text NOT NULL CHECK(checksum ~ '^[a-f0-9]{64}$'),
 file_size bigint NOT NULL CHECK(file_size>0 AND file_size<=33554432),
 manifest jsonb NOT NULL,
 created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
 UNIQUE(run_id,checksum,qa_binding_checksum)
);
CREATE TRIGGER release_candidate_immutable BEFORE UPDATE OR DELETE ON platform.release_candidate_record
 FOR EACH ROW EXECUTE FUNCTION platform.protect_run_approval();
CREATE TABLE platform.release_portability_check (
 check_id uuid PRIMARY KEY,
 candidate_id uuid NOT NULL UNIQUE REFERENCES platform.release_candidate_record(candidate_id),
 claim_token uuid NOT NULL UNIQUE,
 status text NOT NULL CHECK(status IN ('RUNNING','PASS','FAIL','UNKNOWN')),
 evidence jsonb,
 checksum text CHECK(checksum ~ '^[a-f0-9]{64}$'),
 started_at timestamptz NOT NULL DEFAULT clock_timestamp(),
 finished_at timestamptz
);
CREATE FUNCTION platform.protect_release_portability() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
 IF TG_OP='DELETE' THEN RAISE EXCEPTION 'Portability history is immutable'; END IF;
 IF OLD.status<>'RUNNING' OR NEW.status NOT IN ('PASS','FAIL','UNKNOWN')
    OR NEW.finished_at IS NULL OR NEW.evidence IS NULL OR NEW.checksum IS NULL
    OR (to_jsonb(NEW)-ARRAY['status','evidence','checksum','finished_at'])
       IS DISTINCT FROM (to_jsonb(OLD)-ARRAY['status','evidence','checksum','finished_at']) THEN
  RAISE EXCEPTION 'Portability check cannot be replayed';
 END IF;
 RETURN NEW;
END;
$$;
CREATE TRIGGER release_portability_immutable BEFORE UPDATE OR DELETE ON platform.release_portability_check
 FOR EACH ROW EXECUTE FUNCTION platform.protect_release_portability();
CREATE TABLE platform.release_delivery (
 release_id uuid PRIMARY KEY,
 candidate_id uuid NOT NULL UNIQUE REFERENCES platform.release_candidate_record(candidate_id),
 check_id uuid NOT NULL UNIQUE REFERENCES platform.release_portability_check(check_id),
 operator_id uuid NOT NULL REFERENCES platform.operator_profile(operator_id),
 binding jsonb NOT NULL,
 binding_checksum text NOT NULL CHECK(binding_checksum ~ '^[a-f0-9]{64}$'),
 checksum text NOT NULL CHECK(checksum ~ '^[a-f0-9]{64}$'),
 file_size bigint NOT NULL CHECK(file_size>0 AND file_size<=33554432),
 manifest jsonb NOT NULL,
 approved_at timestamptz NOT NULL DEFAULT clock_timestamp()
);
CREATE TRIGGER release_delivery_immutable BEFORE UPDATE OR DELETE ON platform.release_delivery
 FOR EACH ROW EXECUTE FUNCTION platform.protect_run_approval();
