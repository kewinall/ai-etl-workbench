-- A second read of a known-completed execution, never a second Hop dispatch.
CREATE TABLE platform.comparison_recovery (
 recovery_id uuid PRIMARY KEY,
 request_id uuid NOT NULL UNIQUE REFERENCES platform.hop_dispatch_request(request_id),
 run_id uuid NOT NULL UNIQUE REFERENCES platform.task_run(run_id),
 operator_id uuid NOT NULL REFERENCES platform.operator_profile(operator_id),
 binding jsonb NOT NULL CHECK(jsonb_typeof(binding)='object'),
 binding_checksum text NOT NULL CHECK(binding_checksum ~ '^[a-f0-9]{64}$'),
 status text NOT NULL CHECK(status IN ('QUEUED','CLAIMED','COMPLETED','FAILED')),
 claim_token uuid UNIQUE,
 claimed_at timestamptz,
 finished_at timestamptz,
 comparison_id uuid REFERENCES platform.task_run_result_comparison(comparison_id),
 comparison_checksum text CHECK(comparison_checksum ~ '^[a-f0-9]{64}$'),
 outcome_code text,
 created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
 CHECK ((status='COMPLETED')=(comparison_id IS NOT NULL AND comparison_checksum IS NOT NULL)),
 CHECK ((comparison_id IS NULL)=(comparison_checksum IS NULL))
);
CREATE FUNCTION platform.protect_comparison_recovery() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
 IF TG_OP='DELETE' THEN RAISE EXCEPTION 'Comparison recovery history is immutable'; END IF;
 IF (to_jsonb(NEW)-ARRAY['status','claim_token','claimed_at','finished_at','comparison_id','comparison_checksum','outcome_code'])
    IS DISTINCT FROM (to_jsonb(OLD)-ARRAY['status','claim_token','claimed_at','finished_at','comparison_id','comparison_checksum','outcome_code']) THEN
  RAISE EXCEPTION 'Comparison recovery binding is immutable';
 END IF;
 IF OLD.status='QUEUED' AND NEW.status='CLAIMED' AND NEW.claim_token IS NOT NULL
    AND NEW.claimed_at IS NOT NULL AND NEW.finished_at IS NULL AND NEW.outcome_code IS NULL THEN RETURN NEW; END IF;
 IF OLD.status='CLAIMED' AND NEW.status IN ('COMPLETED','FAILED')
    AND NEW.claim_token=OLD.claim_token AND NEW.claimed_at=OLD.claimed_at
    AND NEW.finished_at IS NOT NULL AND NEW.outcome_code IS NOT NULL THEN RETURN NEW; END IF;
 RAISE EXCEPTION 'Comparison recovery cannot be replayed';
END;
$$;
CREATE TRIGGER comparison_recovery_immutable BEFORE UPDATE OR DELETE ON platform.comparison_recovery
 FOR EACH ROW EXECUTE FUNCTION platform.protect_comparison_recovery();
