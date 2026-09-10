ALTER TABLE platform.hop_artifact
  DROP CONSTRAINT IF EXISTS hop_artifact_task_id_artifact_type_version_key;

CREATE UNIQUE INDEX IF NOT EXISTS hop_artifact_task_file_version_uq
  ON platform.hop_artifact(task_id, file_path, version);
