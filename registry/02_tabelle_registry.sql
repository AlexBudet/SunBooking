-- ═══════════════════════════════════════════════════════════════════════
--  REGISTRO CENTRALE TOSCA — tabelle
--  Da eseguire DOPO 01_crea_registry.sql, connessi a "tosca_registry"
--  (in psql:  \c tosca_registry ).
--
--  Verifica di essere nel posto giusto prima di partire:
--      SELECT current_database(), current_user;
--      -- deve dire:  tosca_registry | Alessio
-- ═══════════════════════════════════════════════════════════════════════


-- ═══════════════════════════════════════════════════════════════════════
--  ⚠️  RESET — CANCELLA TUTTI I DATI DEL REGISTRO  ⚠️
--
--  Serve solo per rifare le tabelle da capo mentre lo schema è ancora in
--  costruzione. Finché il registro è vuoto è innocuo e rende lo script
--  rieseguibile a piacere.
--
--  DAL PRIMO CONTRATTO FIRMATO IN POI, CANCELLARE QUESTO BLOCCO:
--  qui dentro ci finiranno i PDF firmati, che vanno conservati 10 anni.
-- ═══════════════════════════════════════════════════════════════════════
DROP TABLE IF EXISTS payment            CASCADE;
DROP TABLE IF EXISTS invoice            CASCADE;
DROP TABLE IF EXISTS billing            CASCADE;
DROP TABLE IF EXISTS contract_signature CASCADE;
DROP TABLE IF EXISTS contract_consent   CASCADE;
DROP TABLE IF EXISTS contract           CASCADE;
DROP TABLE IF EXISTS onboarding_invite  CASCADE;
DROP TABLE IF EXISTS tenant             CASCADE;


-- ── NEGOZI ─────────────────────────────────────────────────────────────
-- Un record per negozio, dal momento dell'invito. idx e db_uri_enc restano
-- NULL finché il tenant non viene creato davvero (provisioning dopo firma
-- e incasso): un database creato per una trattativa non chiusa consuma
-- connessioni sul B1ms che è già stretto.
CREATE TABLE tenant (
    id              serial PRIMARY KEY,
    idx             integer UNIQUE,             -- indice /s/<idx> in wsgi.py
    db_uri_enc      text,                       -- URI cifrata, mai in chiaro
    business_name   varchar(150) NOT NULL,
    status          varchar(20)  NOT NULL DEFAULT 'invited',
    created_at      timestamptz  NOT NULL DEFAULT now(),
    provisioned_at  timestamptz,
    CONSTRAINT tenant_status_ck CHECK (status IN
        ('invited','signed','provisioning','active','suspended','terminated'))
);
CREATE INDEX tenant_status_idx ON tenant (status);


-- ── INVITI DI ATTIVAZIONE ──────────────────────────────────────────────
-- Il token in chiaro vive solo dentro il link consegnato al cliente: qui
-- se ne conserva lo SHA-256, così chi legge il database non può usarlo.
CREATE TABLE onboarding_invite (
    id          serial PRIMARY KEY,
    tenant_id   integer NOT NULL REFERENCES tenant(id) ON DELETE CASCADE,
    token_hash  varchar(64) NOT NULL UNIQUE,
    email       varchar(120),
    expires_at  timestamptz NOT NULL,
    opened_at   timestamptz,
    used_at     timestamptz,
    created_at  timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX onboarding_invite_tenant_idx ON onboarding_invite (tenant_id);


-- ── CONTRATTO ──────────────────────────────────────────────────────────
-- Fonte di verità dei dati raccolti dal form. Al provisioning le colonne
-- anagrafiche vengono copiate in business_info del tenant appena creato.
CREATE TABLE contract (
    id                   serial PRIMARY KEY,
    tenant_id            integer NOT NULL REFERENCES tenant(id) ON DELETE CASCADE,
    status               varchar(20) NOT NULL DEFAULT 'draft',
    contract_version     varchar(20),

    -- anagrafica
    legal_business_name  varchar(150),
    trade_name           varchar(150),
    legal_form           varchar(50),
    vat_number           varchar(20),
    fiscal_code          varchar(16),
    rea_number           varchar(20),
    rea_province         varchar(2),
    pec                  varchar(120),
    sdi_code             varchar(7),

    -- sede legale
    legal_address        varchar(200),
    legal_cap            varchar(10),
    legal_city           varchar(100),
    legal_province       varchar(2),

    -- sede operativa (è questa che finisce in business_info)
    op_same_as_legal     boolean DEFAULT true,
    op_address           varchar(200),
    op_cap               varchar(10),
    op_city              varchar(100),
    op_province          varchar(2),

    -- contatti
    email                varchar(120),
    phone                varchar(30),
    mobile               varchar(30),
    website              varchar(200),

    -- firmatario
    signer_first_name    varchar(80),
    signer_last_name     varchar(80),
    signer_fiscal_code   varchar(16),
    signer_role          varchar(50),
    signer_mobile        varchar(30),          -- utenza per l'OTP
    signer_email         varchar(120),

    -- pre-configurazione dell'istanza
    opening_time         time,                 -- NOT NULL in business_info
    closing_time         time,                 -- NOT NULL in business_info
    closing_days         text,                 -- JSON, stesso formato del tenant
    vat_percentage       numeric(5,2) DEFAULT 22.0,
    operators_count      integer,
    printer_model        varchar(30),
    current_software     varchar(100),
    has_data_to_migrate  boolean,

    -- moduli sottoscritti (diventano i flag di OWNER nel tenant)
    module_base          boolean DEFAULT true,
    module_web           boolean DEFAULT false,
    module_pacchetti     boolean DEFAULT false,
    module_solarium      boolean DEFAULT false,

    -- condizioni economiche, impostate dall'owner all'invito
    starter_total        numeric(10,2),
    saas_monthly_amount  numeric(10,2),

    -- SEPA: mai l'IBAN completo in chiaro
    sepa_mandate_ref     varchar(64),
    sepa_iban_last4      varchar(4),
    sepa_signed_at       timestamptz,

    created_at           timestamptz NOT NULL DEFAULT now(),
    updated_at           timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT contract_status_ck CHECK (status IN ('draft','ready','signed','void'))
);
CREATE INDEX contract_tenant_idx ON contract (tenant_id);


-- ── CONSENSI ───────────────────────────────────────────────────────────
-- Una riga per spunta. Le clausole ex artt. 1341-1342 c.c. richiedono
-- un'accettazione SEPARATA e successiva a quella del contratto: per questo
-- sono righe distinte e non un unico booleano.
CREATE TABLE contract_consent (
    id           serial PRIMARY KEY,
    contract_id  integer NOT NULL REFERENCES contract(id) ON DELETE CASCADE,
    kind         varchar(40) NOT NULL,
    accepted     boolean NOT NULL,
    doc_version  varchar(20),
    doc_sha256   varchar(64),
    accepted_at  timestamptz NOT NULL DEFAULT now(),
    ip           varchar(45),
    user_agent   text,
    CONSTRAINT contract_consent_kind_ck CHECK (kind IN
        ('contract','art1341','dpa','remote_support','not_consumer'))
);
CREATE INDEX contract_consent_contract_idx ON contract_consent (contract_id);


-- ── FIRMA ──────────────────────────────────────────────────────────────
-- pdf_bytes è la copia autorevole: il contratto va conservato 10 anni
-- (art. 2220 c.c.) e non può vivere solo nel database del tenant, che
-- viene dismesso alla cessazione del rapporto. Una copia di cortesia nel
-- tenant si aggiunge dopo, per farla riscaricare al cliente.
CREATE TABLE contract_signature (
    id                 serial PRIMARY KEY,
    contract_id        integer NOT NULL REFERENCES contract(id) ON DELETE CASCADE,
    method             varchar(30) NOT NULL,   -- coupon_infocert | certyneo_aes | otp_interno
    provider           varchar(50),
    provider_envelope  varchar(120),           -- id pratica lato provider
    signed_at          timestamptz,
    ip                 varchar(45),
    user_agent         text,
    pdf_sha256         varchar(64) NOT NULL,
    pdf_bytes          bytea,
    audit_pdf_bytes    bytea,                  -- audit trail del provider
    audit_json         jsonb,
    created_at         timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX contract_signature_contract_idx ON contract_signature (contract_id);


-- ── FATTURAZIONE (migrata da owner_billing.json) ───────────────────────
-- Stessi campi del JSON, così _compliance_status() continua a funzionare
-- senza riscriverne la logica.
CREATE TABLE billing (
    tenant_id            integer PRIMARY KEY REFERENCES tenant(id) ON DELETE CASCADE,
    activation_date      date,
    contract_start_date  date,
    starter_expiry_date  date,
    starter_total        numeric(10,2),
    saas_monthly_amount  numeric(10,2),
    saas_next_renewal    date,
    max_payment_days     integer NOT NULL DEFAULT 15,
    is_owner_db          boolean NOT NULL DEFAULT false,
    einvoice_customer_id varchar(64),
    payment_customer_ref varchar(64),
    updated_at           timestamptz NOT NULL DEFAULT now()
);

-- ATTENZIONE: i nomi delle colonne di invoice e payment ricalcano ESATTAMENTE
-- le chiavi dei dict usati dalle rotte /owner-setup/billing/* in wsgi.py, e
-- l'id resta la stringa uuid4().hex[:10] generata dal codice (non un serial).
-- Devono restare allineati a appl/registry_models.py.
CREATE TABLE invoice (
    id            varchar(32) PRIMARY KEY,
    tenant_id     integer NOT NULL REFERENCES tenant(id) ON DELETE CASCADE,
    date          date,
    number        varchar(50),
    description   text,
    amount        numeric(10,2) NOT NULL DEFAULT 0,
    paid          boolean NOT NULL DEFAULT false,
    einvoice_id   varchar(64),
    einvoice_url  text,
    created_at    timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX invoice_tenant_idx ON invoice (tenant_id);

CREATE TABLE payment (
    id                   varchar(32) PRIMARY KEY,
    tenant_id            integer NOT NULL REFERENCES tenant(id) ON DELETE CASCADE,
    date                 date,
    amount               numeric(10,2) NOT NULL DEFAULT 0,
    method               varchar(40),
    reference            varchar(120),
    provider_payment_id  varchar(64),
    created_at           timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX payment_tenant_idx ON payment (tenant_id);


-- ── VERIFICA FINALE ────────────────────────────────────────────────────
SELECT table_name,
       (SELECT count(*) FROM information_schema.columns c
        WHERE c.table_name = t.table_name AND c.table_schema = 'public') AS colonne
FROM information_schema.tables t
WHERE table_schema = 'public' AND table_type = 'BASE TABLE'
ORDER BY table_name;
-- Attese 8 tabelle: billing, contract, contract_consent, contract_signature,
--                   invoice, onboarding_invite, payment, tenant
