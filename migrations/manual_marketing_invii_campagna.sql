-- Marketing: storico degli invii per promo ("gia' inviata a questo cliente").
-- campagna    = 'tpl:<id template>' | 'preset:<nome>' | NULL (testo libero)
-- azzerato_il = quando l'operatore ha chiuso l'edizione della promo (mai DELETE:
--               marketing_invii conta anche il limite giornaliero)
-- Su ogni negozio, PRIMA del deploy. Idempotente.
ALTER TABLE marketing_invii ADD COLUMN IF NOT EXISTS campagna VARCHAR(60);
ALTER TABLE marketing_invii ADD COLUMN IF NOT EXISTS azzerato_il TIMESTAMP;
CREATE INDEX IF NOT EXISTS ix_marketing_invii_campagna ON marketing_invii (campagna);
