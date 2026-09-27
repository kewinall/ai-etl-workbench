-- Local single-operator declaration, not authenticated identity evidence.
ALTER TABLE platform.pilot_effort_event DROP CONSTRAINT pilot_effort_event_actor_check;
ALTER TABLE platform.pilot_effort_event ADD COLUMN human_attested boolean NOT NULL DEFAULT false;
ALTER TABLE platform.pilot_effort_event ADD CONSTRAINT pilot_effort_actor_declaration CHECK (
 (actor='HUMAN_SELF_REPORTED' AND human_attested) OR
 (actor IN ('DELEGATED_AGENT','FUNCTIONAL_TEST') AND NOT human_attested)
);
