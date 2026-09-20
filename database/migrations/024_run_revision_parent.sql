ALTER TABLE platform.task_run ADD COLUMN parent_run_id uuid REFERENCES platform.task_run(run_id);
CREATE UNIQUE INDEX task_run_one_revision_child ON platform.task_run(parent_run_id) WHERE parent_run_id IS NOT NULL;
CREATE FUNCTION platform.protect_run_parent() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
 IF NEW.parent_run_id IS DISTINCT FROM OLD.parent_run_id THEN
   RAISE EXCEPTION 'Run parent is immutable';
 END IF;
 RETURN NEW;
END;
$$;
CREATE TRIGGER task_run_parent_immutable BEFORE UPDATE ON platform.task_run
 FOR EACH ROW EXECUTE FUNCTION platform.protect_run_parent();
