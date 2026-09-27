-- A prospective, fixed denominator. Registration is not execution evidence.
CREATE TABLE platform.pilot_cohort (
 cohort_id uuid PRIMARY KEY,
 project_id uuid NOT NULL REFERENCES platform.project(project_id),
 name text NOT NULL,
 protocol_version text NOT NULL CHECK(protocol_version='pilot-v1'),
 plan_checksum char(64) NOT NULL,
 created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
 UNIQUE(project_id,plan_checksum)
);
CREATE TABLE platform.pilot_cohort_case (
 cohort_id uuid NOT NULL REFERENCES platform.pilot_cohort(cohort_id),
 case_key text NOT NULL,
 ordinal integer NOT NULL CHECK(ordinal BETWEEN 1 AND 20),
 definition jsonb NOT NULL,
 PRIMARY KEY(cohort_id,case_key),
 UNIQUE(cohort_id,ordinal)
);
CREATE TRIGGER pilot_cohort_immutable BEFORE UPDATE OR DELETE ON platform.pilot_cohort
 FOR EACH ROW EXECUTE FUNCTION platform.protect_run_approval();
CREATE TRIGGER pilot_cohort_case_immutable BEFORE UPDATE OR DELETE ON platform.pilot_cohort_case
 FOR EACH ROW EXECUTE FUNCTION platform.protect_run_approval();
