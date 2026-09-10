ALTER TABLE platform.model_usage ADD COLUMN IF NOT EXISTS nano_aiu bigint;
ALTER TABLE platform.model_usage ADD COLUMN IF NOT EXISTS ai_credits numeric(20,9);
ALTER TABLE platform.model_usage ADD COLUMN IF NOT EXISTS premium_requests numeric(20,4);

UPDATE platform.model_usage
   SET premium_requests = (raw_usage->>'premium_requests')::numeric
 WHERE premium_requests IS NULL
   AND raw_usage->>'premium_requests' IS NOT NULL;
