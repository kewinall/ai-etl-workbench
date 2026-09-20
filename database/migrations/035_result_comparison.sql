CREATE TABLE platform.task_run_result_comparison (
 comparison_id uuid PRIMARY KEY,
 run_id uuid NOT NULL REFERENCES platform.task_run(run_id) ON DELETE CASCADE,
 checksum text NOT NULL CHECK(checksum ~ '^[a-f0-9]{64}$'),
 evidence jsonb NOT NULL CHECK(jsonb_typeof(evidence)='object'),
 created_at timestamptz NOT NULL DEFAULT now(),
 UNIQUE(run_id,checksum),
 CHECK(evidence ?& ARRAY['actual_provenance','qa_passed','release_ready','status']),
 CHECK(octet_length(evidence::text)<=16384),
 CHECK(evidence->>'actual_provenance'='NOT_VERIFIED'),
 CHECK(evidence->'qa_passed'='false'::jsonb),
 CHECK(evidence->'release_ready'='false'::jsonb),
 CHECK(evidence->>'status' IN ('MATCH','MISMATCH'))
);
CREATE TRIGGER result_comparison_immutable BEFORE UPDATE ON platform.task_run_result_comparison
 FOR EACH ROW EXECUTE FUNCTION platform.protect_run_approval();
