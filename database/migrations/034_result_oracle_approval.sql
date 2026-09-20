CREATE TABLE platform.result_oracle_approval (
 approval_id uuid PRIMARY KEY,
 oracle_id uuid NOT NULL UNIQUE REFERENCES platform.result_oracle(oracle_id) ON DELETE CASCADE,
 operator_id uuid NOT NULL REFERENCES platform.operator_profile(operator_id),
 document_checksum text NOT NULL CHECK(document_checksum ~ '^[a-f0-9]{64}$'),
 created_at timestamptz NOT NULL DEFAULT now()
);
CREATE TRIGGER result_oracle_approval_immutable BEFORE UPDATE ON platform.result_oracle_approval
 FOR EACH ROW EXECUTE FUNCTION platform.protect_run_approval();
