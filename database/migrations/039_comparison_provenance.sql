CREATE TABLE platform.result_comparison_provenance (
 comparison_id uuid PRIMARY KEY REFERENCES platform.task_run_result_comparison(comparison_id),
 run_id uuid NOT NULL REFERENCES platform.task_run_target_claim(run_id),
 comparison_checksum text NOT NULL CHECK(comparison_checksum ~ '^[a-f0-9]{64}$'),
 query_checksum text NOT NULL CHECK(query_checksum ~ '^[a-f0-9]{64}$'),
 settings_checksum text NOT NULL CHECK(settings_checksum ~ '^[a-f0-9]{64}$'),
 empty_checked_at timestamptz NOT NULL,
 hop_event_id bigint NOT NULL REFERENCES platform.task_run_event(event_id),
 checked_at timestamptz NOT NULL DEFAULT clock_timestamp()
);
CREATE TRIGGER comparison_provenance_immutable BEFORE UPDATE OR DELETE ON platform.result_comparison_provenance
 FOR EACH ROW EXECUTE FUNCTION platform.protect_run_approval();
