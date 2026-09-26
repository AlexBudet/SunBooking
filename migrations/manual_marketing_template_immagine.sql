-- Marketing: foto allegata ai template WhatsApp (ridimensionata dal programma).
-- Su ogni negozio, PRIMA del deploy. Idempotente.
ALTER TABLE marketing_templates ADD COLUMN IF NOT EXISTS immagine BYTEA;
ALTER TABLE marketing_templates ADD COLUMN IF NOT EXISTS immagine_mime VARCHAR(50);
