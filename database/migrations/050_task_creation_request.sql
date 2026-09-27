CREATE TABLE platform.task_creation_request (
    project_id uuid NOT NULL REFERENCES platform.project(project_id),
    request_key uuid NOT NULL,
    payload_checksum char(64) NOT NULL,
    task_id text NOT NULL REFERENCES platform.task(task_id) ON DELETE CASCADE,
    created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    PRIMARY KEY (project_id, request_key)
);
