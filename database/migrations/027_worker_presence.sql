CREATE TABLE platform.worker_presence (
 instance_id uuid PRIMARY KEY,
 kind text NOT NULL CHECK (kind IN ('CONTROL','SA_LITELLM','SA_COPILOT')),
 mode text NOT NULL CHECK (mode IN ('EXECUTE','OBSERVE')),
 activity text NOT NULL CHECK (activity IN ('IDLE','BUSY','STOPPED')),
 protocol_version integer NOT NULL DEFAULT 1 CHECK (protocol_version=1),
 started_at timestamptz NOT NULL DEFAULT clock_timestamp(),
 last_seen timestamptz NOT NULL DEFAULT clock_timestamp()
);
CREATE INDEX worker_presence_kind_seen ON platform.worker_presence(kind,last_seen);
