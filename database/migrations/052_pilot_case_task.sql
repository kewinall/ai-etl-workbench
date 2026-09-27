CREATE TABLE platform.pilot_case_task (
 cohort_id uuid NOT NULL,
 case_key text NOT NULL,
 task_id text NOT NULL UNIQUE REFERENCES platform.task(task_id),
 enrolled_at timestamptz NOT NULL DEFAULT clock_timestamp(),
 PRIMARY KEY(cohort_id,case_key),
 FOREIGN KEY(cohort_id,case_key) REFERENCES platform.pilot_cohort_case(cohort_id,case_key)
);
CREATE FUNCTION platform.check_pilot_task_enrollment() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE task_project uuid; cohort_project uuid;
BEGIN
 SELECT project_id INTO task_project FROM platform.task WHERE task_id=NEW.task_id FOR UPDATE;
 SELECT project_id INTO cohort_project FROM platform.pilot_cohort WHERE cohort_id=NEW.cohort_id;
 IF task_project IS NULL OR cohort_project IS NULL OR task_project<>cohort_project THEN
  RAISE EXCEPTION 'PILOT_PROJECT_MISMATCH';
 END IF;
 IF EXISTS(SELECT 1 FROM platform.task_run WHERE task_id=NEW.task_id) THEN
  RAISE EXCEPTION 'PILOT_TASK_ALREADY_STARTED';
 END IF;
 RETURN NEW;
END;
$$;
CREATE TRIGGER pilot_case_task_guard BEFORE INSERT ON platform.pilot_case_task
 FOR EACH ROW EXECUTE FUNCTION platform.check_pilot_task_enrollment();
CREATE TRIGGER pilot_case_task_immutable BEFORE UPDATE OR DELETE ON platform.pilot_case_task
 FOR EACH ROW EXECUTE FUNCTION platform.protect_run_approval();
CREATE FUNCTION platform.protect_pilot_task_project() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
 IF NEW.project_id IS DISTINCT FROM OLD.project_id AND
    EXISTS(SELECT 1 FROM platform.pilot_case_task WHERE task_id=OLD.task_id) THEN
  RAISE EXCEPTION 'PILOT_TASK_PROJECT_IMMUTABLE';
 END IF;
 RETURN NEW;
END;
$$;
CREATE TRIGGER pilot_task_project_guard BEFORE UPDATE ON platform.task
 FOR EACH ROW EXECUTE FUNCTION platform.protect_pilot_task_project();
