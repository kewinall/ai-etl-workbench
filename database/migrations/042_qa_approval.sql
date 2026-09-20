CREATE TABLE platform.qa_review_approval (
 approval_id uuid PRIMARY KEY,
 run_id uuid NOT NULL UNIQUE REFERENCES platform.task_run(run_id),
 invocation_id uuid NOT NULL UNIQUE REFERENCES platform.agent_invocation(invocation_id),
 operator_id uuid NOT NULL REFERENCES platform.operator_profile(operator_id),
 binding jsonb NOT NULL,
 binding_checksum text NOT NULL CHECK(binding_checksum ~ '^[a-f0-9]{64}$'),
 created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
 CHECK(jsonb_typeof(binding)='object'),
 CHECK(binding ?& ARRAY['run_id','invocation_id','checksum']),
 CHECK(jsonb_typeof(binding->'run_id')='string' AND jsonb_typeof(binding->'invocation_id')='string'
   AND jsonb_typeof(binding->'checksum')='string'),
 CHECK(binding->>'run_id'=run_id::text),
 CHECK(binding->>'invocation_id'=invocation_id::text),
 CHECK(binding->>'checksum'=binding_checksum)
);
CREATE TRIGGER qa_review_approval_immutable BEFORE UPDATE OR DELETE ON platform.qa_review_approval
 FOR EACH ROW EXECUTE FUNCTION platform.protect_run_approval();
