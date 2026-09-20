CREATE TABLE platform.hop_dispatch_request (
 request_id uuid PRIMARY KEY,
 run_id uuid NOT NULL UNIQUE REFERENCES platform.task_run(run_id),
 authorization_id uuid NOT NULL UNIQUE REFERENCES platform.task_run_execution_authorization(authorization_id),
 specification_id uuid NOT NULL REFERENCES platform.specification(specification_id),
 binding jsonb NOT NULL CHECK(jsonb_typeof(binding)='object'),
 binding_checksum text NOT NULL CHECK(binding_checksum ~ '^[a-f0-9]{64}$'),
 status text NOT NULL CHECK(status IN ('QUEUED','CLAIMED','COMPLETED','NEEDS_REVIEW')),
 claim_token uuid UNIQUE,
 claimed_at timestamptz,
 finished_at timestamptz,
 outcome_code text,
 created_at timestamptz NOT NULL DEFAULT clock_timestamp()
);
CREATE FUNCTION platform.protect_hop_dispatch() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
 IF TG_OP='DELETE' THEN RAISE EXCEPTION 'Hop dispatch history is immutable'; END IF;
 IF (to_jsonb(NEW)-ARRAY['status','claim_token','claimed_at','finished_at','outcome_code'])
      IS DISTINCT FROM (to_jsonb(OLD)-ARRAY['status','claim_token','claimed_at','finished_at','outcome_code']) THEN
  RAISE EXCEPTION 'Hop dispatch binding is immutable';
 END IF;
 IF OLD.status='QUEUED' AND NEW.status='CLAIMED' AND NEW.claim_token IS NOT NULL AND NEW.claimed_at IS NOT NULL
    AND NEW.finished_at IS NULL AND NEW.outcome_code IS NULL THEN RETURN NEW; END IF;
 IF OLD.status='CLAIMED' AND NEW.status IN ('COMPLETED','NEEDS_REVIEW')
    AND NEW.claim_token=OLD.claim_token AND NEW.claimed_at=OLD.claimed_at
    AND NEW.finished_at IS NOT NULL AND NEW.outcome_code IS NOT NULL THEN RETURN NEW; END IF;
 RAISE EXCEPTION 'Hop dispatch cannot be replayed';
END;
$$;
CREATE TRIGGER hop_dispatch_immutable BEFORE UPDATE OR DELETE ON platform.hop_dispatch_request
 FOR EACH ROW EXECUTE FUNCTION platform.protect_hop_dispatch();
