CREATE TABLE platform.task_run_execution_authorization (
 authorization_id uuid PRIMARY KEY,
 run_id uuid NOT NULL UNIQUE REFERENCES platform.task_run(run_id),
 specification_id uuid NOT NULL REFERENCES platform.specification(specification_id),
 operator_id uuid NOT NULL REFERENCES platform.operator_profile(operator_id),
 binding jsonb NOT NULL CHECK(jsonb_typeof(binding)='object'),
 binding_checksum text NOT NULL CHECK(binding_checksum ~ '^[a-f0-9]{64}$'),
 created_at timestamptz NOT NULL DEFAULT now(),
 expires_at timestamptz NOT NULL DEFAULT (now() + interval '30 minutes'),
 CHECK(expires_at > created_at)
);
CREATE TRIGGER execution_authorization_immutable
 BEFORE UPDATE ON platform.task_run_execution_authorization
 FOR EACH ROW EXECUTE FUNCTION platform.protect_run_approval();
