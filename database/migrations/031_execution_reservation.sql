CREATE TABLE platform.task_run_execution_reservation (
 reservation_id uuid PRIMARY KEY,
 authorization_id uuid NOT NULL UNIQUE REFERENCES platform.task_run_execution_authorization(authorization_id),
 run_id uuid NOT NULL UNIQUE REFERENCES platform.task_run(run_id),
 binding_checksum text NOT NULL CHECK(binding_checksum ~ '^[a-f0-9]{64}$'),
 created_at timestamptz NOT NULL DEFAULT now()
);
CREATE TRIGGER execution_reservation_immutable BEFORE UPDATE ON platform.task_run_execution_reservation
 FOR EACH ROW EXECUTE FUNCTION platform.protect_run_approval();
