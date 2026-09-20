CREATE UNIQUE INDEX qa_one_intent_per_run ON platform.agent_invocation(run_id) WHERE role='pilot_qa';
CREATE FUNCTION platform.protect_qa_invocation() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
 IF OLD.role='pilot_qa' THEN
  IF TG_OP='DELETE' THEN RAISE EXCEPTION 'QA history is immutable'; END IF;
  IF OLD.status<>'QA_RESERVED'
   OR NEW.status NOT IN ('VALIDATED_NOT_APPROVED','STALE_RESULT_NEEDS_REVIEW','QA_OUTCOME_UNKNOWN')
   OR (to_jsonb(NEW)-ARRAY['status','output_json','duration_ms'])
       IS DISTINCT FROM (to_jsonb(OLD)-ARRAY['status','output_json','duration_ms']) THEN
   RAISE EXCEPTION 'QA intent and completed history are immutable';
  END IF;
 END IF;
 IF TG_OP='DELETE' THEN RETURN OLD; END IF;
 RETURN NEW;
END;
$$;
CREATE TRIGGER qa_invocation_immutable BEFORE UPDATE OR DELETE ON platform.agent_invocation
 FOR EACH ROW EXECUTE FUNCTION platform.protect_qa_invocation();
