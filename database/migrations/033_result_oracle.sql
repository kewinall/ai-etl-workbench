CREATE TABLE platform.result_oracle (
 oracle_id uuid PRIMARY KEY,
 specification_id uuid NOT NULL REFERENCES platform.specification(specification_id) ON DELETE CASCADE,
 version integer NOT NULL CHECK(version > 0),
 document_checksum text NOT NULL CHECK(document_checksum ~ '^[a-f0-9]{64}$'),
 specification_checksum text NOT NULL CHECK(specification_checksum ~ '^[a-f0-9]{64}$'),
 naming_checksum text NOT NULL CHECK(naming_checksum ~ '^[a-f0-9]{64}$'),
 cipher_text bytea NOT NULL CHECK(octet_length(cipher_text) <= 16777216),
 nonce bytea NOT NULL CHECK(octet_length(nonce)=12),
 size integer NOT NULL CHECK(size BETWEEN 1 AND 8388608),
 created_at timestamptz NOT NULL DEFAULT now(),
 UNIQUE(specification_id, version)
);
CREATE TRIGGER result_oracle_immutable BEFORE UPDATE ON platform.result_oracle
 FOR EACH ROW EXECUTE FUNCTION platform.protect_run_approval();
