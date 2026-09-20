CREATE TABLE platform.qa_dispatch_claim (
 invocation_id uuid PRIMARY KEY REFERENCES platform.agent_invocation(invocation_id),
 claim_token uuid NOT NULL UNIQUE,
 created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
 expires_at timestamptz NOT NULL DEFAULT clock_timestamp()+interval '10 minutes'
);
CREATE TRIGGER qa_dispatch_claim_immutable BEFORE UPDATE OR DELETE ON platform.qa_dispatch_claim
 FOR EACH ROW EXECUTE FUNCTION platform.protect_run_approval();
