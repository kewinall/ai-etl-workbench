-- Server-recorded prospective intervals. No historical timestamp import.
CREATE TABLE platform.pilot_effort_event (
 sequence bigint PRIMARY KEY CHECK(sequence>0),
 request_key text NOT NULL UNIQUE CHECK(length(request_key) BETWEEN 8 AND 160),
 session_id uuid NOT NULL,
 cohort_id uuid NOT NULL,
 case_key text NOT NULL,
 protocol_checksum char(64) NOT NULL CHECK(protocol_checksum ~ '^[a-f0-9]{64}$'),
 actor text NOT NULL CHECK(actor IN ('DELEGATED_AGENT','FUNCTIONAL_TEST')),
 mode text NOT NULL CHECK(mode IN ('WORKBENCH','MANUAL_BASELINE')),
 action text NOT NULL CHECK(action IN ('START','STOP','ABANDON')),
 recorded_at timestamptz NOT NULL DEFAULT clock_timestamp(),
 FOREIGN KEY(cohort_id,case_key) REFERENCES platform.pilot_cohort_case(cohort_id,case_key)
);
CREATE UNIQUE INDEX effort_one_start ON platform.pilot_effort_event(session_id) WHERE action='START';
CREATE UNIQUE INDEX effort_one_end ON platform.pilot_effort_event(session_id) WHERE action<>'START';
CREATE TRIGGER effort_event_immutable BEFORE UPDATE OR DELETE ON platform.pilot_effort_event
 FOR EACH ROW EXECUTE FUNCTION platform.protect_run_approval();
