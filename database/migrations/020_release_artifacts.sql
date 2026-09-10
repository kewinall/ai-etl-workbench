BEGIN;
CREATE TABLE IF NOT EXISTS platform.sdm_artifact (
  sdm_id uuid PRIMARY KEY, task_id text NOT NULL REFERENCES platform.task(task_id) ON DELETE CASCADE,
  file_path text NOT NULL, checksum text NOT NULL, created_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS platform.release (
  release_id uuid PRIMARY KEY, task_id text NOT NULL REFERENCES platform.task(task_id) ON DELETE CASCADE,
  status text NOT NULL CHECK(status IN ('RELEASE_READY','FAILED')), file_path text, manifest jsonb NOT NULL, created_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS platform.release_artifact (
  release_id uuid NOT NULL REFERENCES platform.release(release_id) ON DELETE CASCADE,
  artifact_name text NOT NULL, artifact_type text NOT NULL, checksum text NOT NULL, PRIMARY KEY(release_id,artifact_name)
);
COMMIT;
