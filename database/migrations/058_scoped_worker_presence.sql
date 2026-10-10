-- Liveness metadata only. No workflow, approval or execution authority.
ALTER TABLE platform.worker_presence DROP CONSTRAINT worker_presence_kind_check;
ALTER TABLE platform.worker_presence ADD CONSTRAINT worker_presence_kind_check
 CHECK(kind IN ('CONTROL','SA_LITELLM','SA_COPILOT','DEVELOPER_COPILOT','QA_COPILOT','HOP','PORTABILITY'));
ALTER TABLE platform.worker_presence ADD COLUMN project_id uuid REFERENCES platform.project(project_id);
