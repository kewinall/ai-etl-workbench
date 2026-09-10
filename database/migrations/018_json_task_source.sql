ALTER TABLE platform.task DROP CONSTRAINT IF EXISTS task_source_type_check;
ALTER TABLE platform.task ADD CONSTRAINT task_source_type_check
  CHECK (source_type IN ('CSV','EXCEL','JSON','VERTICA','MIXED','POSTGRESQL_TABLE'));
