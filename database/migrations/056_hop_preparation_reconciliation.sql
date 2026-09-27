CREATE TABLE platform.hop_preparation_reconciliation (
 reconciliation_id uuid PRIMARY KEY,
 request_id uuid NOT NULL UNIQUE REFERENCES platform.hop_dispatch_request(request_id),
 operator_id uuid NOT NULL REFERENCES platform.operator_profile(operator_id),
 binding jsonb NOT NULL,
 binding_checksum text NOT NULL CHECK(binding_checksum ~ '^[a-f0-9]{64}$'),
 evidence_sha256 text NOT NULL CHECK(evidence_sha256 ~ '^[a-f0-9]{64}$'),
 target_exists boolean NOT NULL,
 observed_row_count bigint CHECK(observed_row_count >= 0),
 created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
 CHECK ((target_exists AND observed_row_count IS NOT NULL) OR
        (NOT target_exists AND observed_row_count IS NULL))
);
CREATE TRIGGER hop_preparation_reconciliation_immutable
 BEFORE UPDATE OR DELETE ON platform.hop_preparation_reconciliation
 FOR EACH ROW EXECUTE FUNCTION platform.protect_run_approval();
