-- Prospective only: never infer historical ordering from timestamps or UUIDs.
CREATE TABLE platform.pilot_case_attempt (
 run_id uuid PRIMARY KEY REFERENCES platform.task_run(run_id),
 cohort_id uuid NOT NULL,
 case_key text NOT NULL,
 attempt_ordinal integer NOT NULL CHECK (attempt_ordinal > 0),
 recorded_at timestamptz NOT NULL DEFAULT clock_timestamp(),
 UNIQUE(cohort_id,case_key,attempt_ordinal),
 FOREIGN KEY(cohort_id,case_key) REFERENCES platform.pilot_case_task(cohort_id,case_key)
);

CREATE FUNCTION platform.record_pilot_attempt() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE membership platform.pilot_case_task%ROWTYPE; next_ordinal integer;
BEGIN
 -- Same lock as enqueue, revise and enrollment, including concurrent callers.
 PERFORM 1 FROM platform.task WHERE task_id=NEW.task_id FOR UPDATE;
 SELECT * INTO membership FROM platform.pilot_case_task WHERE task_id=NEW.task_id;
 IF FOUND THEN
  -- Existing pre-migration Run history cannot acquire invented ordinal numbers.
  IF EXISTS(SELECT 1 FROM platform.task_run r
            LEFT JOIN platform.pilot_case_attempt a USING(run_id)
            WHERE r.task_id=NEW.task_id AND r.run_id<>NEW.run_id AND a.run_id IS NULL) THEN
   RAISE EXCEPTION 'PILOT_ATTEMPT_HISTORY_UNORDERED';
  END IF;
  SELECT coalesce(max(attempt_ordinal),0)+1 INTO next_ordinal
   FROM platform.pilot_case_attempt
   WHERE cohort_id=membership.cohort_id AND case_key=membership.case_key;
  INSERT INTO platform.pilot_case_attempt(run_id,cohort_id,case_key,attempt_ordinal)
   VALUES(NEW.run_id,membership.cohort_id,membership.case_key,next_ordinal);
 END IF;
 RETURN NEW;
END;
$$;
CREATE TRIGGER pilot_attempt_after_run AFTER INSERT ON platform.task_run
 FOR EACH ROW EXECUTE FUNCTION platform.record_pilot_attempt();
CREATE TRIGGER pilot_attempt_immutable BEFORE UPDATE OR DELETE ON platform.pilot_case_attempt
 FOR EACH ROW EXECUTE FUNCTION platform.protect_run_approval();
