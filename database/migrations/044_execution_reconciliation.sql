CREATE TABLE platform.execution_reconciliation (
 reconciliation_id uuid PRIMARY KEY,
 run_id uuid NOT NULL UNIQUE REFERENCES platform.task_run(run_id),
 operator_id uuid NOT NULL REFERENCES platform.operator_profile(operator_id),
 binding jsonb NOT NULL CHECK(jsonb_typeof(binding)='object'),
 binding_checksum text NOT NULL CHECK(binding_checksum ~ '^[a-f0-9]{64}$'),
 evidence_sha256 text NOT NULL CHECK(evidence_sha256 ~ '^[a-f0-9]{64}$'),
 observed_row_count bigint NOT NULL CHECK(observed_row_count>=0),
 created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
 CHECK(binding ?& ARRAY['run_id','checksum','outcome_code']),
 CHECK(binding->>'run_id'=run_id::text),
 CHECK(binding->>'checksum'=binding_checksum)
);
CREATE TRIGGER execution_reconciliation_immutable BEFORE UPDATE OR DELETE ON platform.execution_reconciliation
 FOR EACH ROW EXECUTE FUNCTION platform.protect_run_approval();
