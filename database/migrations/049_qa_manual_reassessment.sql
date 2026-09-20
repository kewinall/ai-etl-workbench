-- Preserve every terminal review. A new prompt version needs fresh explicit consent.
DROP INDEX platform.qa_one_intent_per_run;
CREATE UNIQUE INDEX qa_one_intent_per_prompt_version
 ON platform.agent_invocation(run_id,prompt_version) WHERE role='pilot_qa';
