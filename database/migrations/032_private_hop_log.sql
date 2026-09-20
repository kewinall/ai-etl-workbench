CREATE TABLE platform.task_run_private_log (
 run_id uuid PRIMARY KEY REFERENCES platform.task_run(run_id) ON DELETE CASCADE,
 cipher_text bytea NOT NULL CHECK(octet_length(cipher_text) <= 20971520),
 nonce bytea NOT NULL CHECK(octet_length(nonce)=12),
 checksum text NOT NULL CHECK(checksum ~ '^[a-f0-9]{64}$'),
 size integer NOT NULL CHECK(size BETWEEN 0 AND 10485760),
 created_at timestamptz NOT NULL DEFAULT now()
);
CREATE TRIGGER private_hop_log_immutable BEFORE UPDATE ON platform.task_run_private_log
 FOR EACH ROW EXECUTE FUNCTION platform.protect_run_approval();
