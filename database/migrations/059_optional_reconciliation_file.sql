-- Operator confirmation does not require a separately prepared evidence file.
-- Preserve existing immutable receipts and their original fingerprints.
ALTER TABLE platform.execution_reconciliation ALTER COLUMN evidence_sha256 DROP NOT NULL;
ALTER TABLE platform.hop_preparation_reconciliation ALTER COLUMN evidence_sha256 DROP NOT NULL;
