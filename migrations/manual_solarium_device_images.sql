-- ============================================================================
-- Solarium: immagine per ogni macchinario (lampada) mostrata sui tasti della
-- barra "Monitor Lampade" del Calendario (max 60x60 px a video).
--
-- Le immagini sono poche e piccole (ridimensionate a max 120x120 px e
-- ricompresse PNG/WebP lato server), quindi vengono salvate direttamente sul
-- database invece che su filesystem.
--
-- Eseguire UNA VOLTA sul database PostgreSQL (Azure), su ogni negozio.
-- Idempotente: usa IF NOT EXISTS, puoi rilanciarlo senza danni.
-- ============================================================================

ALTER TABLE solarium_devices
    ADD COLUMN IF NOT EXISTS immagine BYTEA;

ALTER TABLE solarium_devices
    ADD COLUMN IF NOT EXISTS immagine_mime VARCHAR(50);
