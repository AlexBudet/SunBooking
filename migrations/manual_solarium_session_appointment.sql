-- ============================================================================
-- Solarium: collegamento diretto seduta -> appuntamento di calendario.
--
-- Le sedute (solarium_sessions) erano gia' collegabili a scontrino
-- (receipt_id) e cliente (client_id); l'appuntamento era ricavabile solo
-- indirettamente leggendo le voci JSON dello scontrino collegato. Questa
-- colonna lo rende un collegamento diretto, per query/report piu' semplici.
--
-- Eseguire UNA VOLTA sul database PostgreSQL (Azure), su ogni negozio.
-- Idempotente: usa IF NOT EXISTS, puoi rilanciarlo senza danni.
-- ============================================================================

ALTER TABLE solarium_sessions
    ADD COLUMN IF NOT EXISTS appointment_id INTEGER REFERENCES appuntamenti(id);
