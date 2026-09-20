ALTER TABLE platform.agent_invocation
 ADD COLUMN claim_token uuid,
 ADD COLUMN lease_until timestamptz,
 ADD COLUMN dispatch_deadline timestamptz;
CREATE INDEX agent_invocation_sa_pending ON platform.agent_invocation(created_at)
 WHERE role='pilot_sa' AND status IN ('SA_QUEUED','DISPATCH_RESERVED');
CREATE FUNCTION platform.protect_sa_authorization() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
 IF OLD.role='pilot_sa' AND (NEW.input_json IS DISTINCT FROM OLD.input_json
   OR NEW.run_id IS DISTINCT FROM OLD.run_id OR NEW.task_id IS DISTINCT FROM OLD.task_id
   OR NEW.role IS DISTINCT FROM OLD.role OR NEW.context_checksum IS DISTINCT FROM OLD.context_checksum
   OR NEW.model IS DISTINCT FROM OLD.model OR NEW.provider IS DISTINCT FROM OLD.provider
   OR NEW.prompt_version IS DISTINCT FROM OLD.prompt_version) THEN
  RAISE EXCEPTION 'SA authorization and context are immutable';
 END IF;
 RETURN NEW;
END;
$$;
CREATE TRIGGER sa_authorization_immutable BEFORE UPDATE ON platform.agent_invocation
 FOR EACH ROW EXECUTE FUNCTION platform.protect_sa_authorization();
