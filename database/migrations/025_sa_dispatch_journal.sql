ALTER TABLE platform.agent_invocation ADD COLUMN run_id uuid REFERENCES platform.task_run(run_id);
CREATE UNIQUE INDEX agent_invocation_one_pilot_sa ON platform.agent_invocation(run_id)
 WHERE role='pilot_sa' AND run_id IS NOT NULL;
