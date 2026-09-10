ALTER TABLE platform.task DROP CONSTRAINT IF EXISTS task_source_type_check;
ALTER TABLE platform.task ADD CONSTRAINT task_source_type_check
  CHECK (source_type IN ('CSV','EXCEL','VERTICA','MIXED','POSTGRESQL_TABLE'));

CREATE TABLE IF NOT EXISTS platform.requirement_issue (
  issue_id uuid PRIMARY KEY,
  task_id text NOT NULL REFERENCES platform.task(task_id),
  specification_id uuid REFERENCES platform.specification(specification_id),
  severity text NOT NULL CHECK (severity IN ('BLOCKING','WARNING','INFERRED','REVIEW_REQUIRED')),
  field_path text NOT NULL,
  reason text NOT NULL,
  candidates jsonb NOT NULL DEFAULT '[]',
  suggested_default jsonb,
  resolved_value jsonb,
  created_at timestamptz NOT NULL DEFAULT now(),
  resolved_at timestamptz
);

CREATE INDEX IF NOT EXISTS requirement_issue_task_idx ON platform.requirement_issue(task_id, created_at);
