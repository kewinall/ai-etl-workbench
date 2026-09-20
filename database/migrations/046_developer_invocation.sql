CREATE UNIQUE INDEX developer_one_intent_per_run ON platform.agent_invocation(run_id)
 WHERE role='pilot_developer';
CREATE FUNCTION platform.protect_developer_invocation() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
 IF OLD.role='pilot_developer' THEN
  IF TG_OP='DELETE' THEN RAISE EXCEPTION 'Developer history is immutable'; END IF;
  IF OLD.status<>'DEVELOPER_RESERVED'
   OR NEW.status NOT IN ('VALIDATED_NOT_APPROVED','STALE_RESULT_NEEDS_REVIEW','DEVELOPER_OUTCOME_UNKNOWN')
   OR (to_jsonb(NEW)-ARRAY['status','output_json','duration_ms'])
       IS DISTINCT FROM (to_jsonb(OLD)-ARRAY['status','output_json','duration_ms']) THEN
   RAISE EXCEPTION 'Developer intent and completed history are immutable';
  END IF;
 END IF;
 IF TG_OP='DELETE' THEN RETURN OLD; END IF;
 RETURN NEW;
END;
$$;
CREATE TRIGGER developer_invocation_immutable BEFORE UPDATE OR DELETE ON platform.agent_invocation
 FOR EACH ROW EXECUTE FUNCTION platform.protect_developer_invocation();
CREATE TABLE platform.developer_dispatch_claim (
 invocation_id uuid PRIMARY KEY REFERENCES platform.agent_invocation(invocation_id),
 claim_token uuid NOT NULL UNIQUE,
 created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
 expires_at timestamptz NOT NULL DEFAULT clock_timestamp()+interval '10 minutes'
);
CREATE TRIGGER developer_dispatch_claim_immutable BEFORE UPDATE OR DELETE ON platform.developer_dispatch_claim
 FOR EACH ROW EXECUTE FUNCTION platform.protect_run_approval();
