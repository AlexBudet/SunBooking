"""
Registro centrale Tosca — modelli e sessione.

Database `tosca_registry`: contiene i dati SUI negozi (contratti, firme,
fatturazione), non i dati DEI negozi. Quelli restano nei database tenant.

Perche' un modulo separato e non `appl/models.py`:

  L'istanza `db` di Flask-SQLAlchemy e' legata all'app corrente, e in
  produzione ogni child app di wsgi.py punta al database di UN tenant. Usare
  `db` per il registro significherebbe scrivere i dati di fatturazione dentro
  il database del negozio che sta servendo la richiesta in quel momento.

  Qui c'e' quindi un engine dedicato, indipendente da Flask: lo usa la root
  app di wsgi.py (owner-setup, form di attivazione, webhook firma). I due
  mondi non si toccano mai, e non e' possibile confonderli per sbaglio.

Se REGISTRY_DATABASE_URI non e' configurata il modulo si carica lo stesso e
`registry_enabled()` risponde False: l'app continua a funzionare, le funzioni
che dipendono dal registro si disattivano da sole.
"""

import os
from contextlib import contextmanager

from sqlalchemy import (
    Boolean, CheckConstraint, Column, Date, DateTime, ForeignKey, Integer,
    LargeBinary, Numeric, String, Text, Time, create_engine, func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import declarative_base, deferred, sessionmaker

Base = declarative_base()

_engine = None
_Session = None


def registry_uri():
    """URI del registro, None se non configurata."""
    uri = os.getenv('REGISTRY_DATABASE_URI')
    return uri if uri and uri.startswith('postgresql') else None


def registry_enabled():
    return registry_uri() is not None


def get_engine():
    """Engine del registro, creato al primo uso.

    Pool volutamente minuscolo: il PostgreSQL B1ms regge ~35 connessioni
    utente (40 usabili sulle 50 dichiarate) e ogni tenant ne tiene gia' 2+1
    per processo, cioe' ~4 a regime fra exe del salone e cloud. Il registro
    fa poche richieste, brevi, e le fa solo il processo cloud.
    """
    global _engine, _Session
    if _engine is None:
        uri = registry_uri()
        if not uri:
            raise RuntimeError(
                "REGISTRY_DATABASE_URI non configurata: il registro centrale "
                "non e' disponibile."
            )
        _engine = create_engine(
            uri,
            pool_size=2,
            max_overflow=1,
            pool_timeout=10,
            pool_recycle=360,
            pool_pre_ping=True,
            future=True,
        )
        _Session = sessionmaker(bind=_engine, future=True, expire_on_commit=False)
    return _engine


@contextmanager
def registry_session():
    """Sessione con commit/rollback automatici.

        with registry_session() as s:
            s.add(Tenant(business_name='...'))
    """
    get_engine()
    session = _Session()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


# ═══════════════════════════════════════════════════════════════════════
#  NEGOZI
# ═══════════════════════════════════════════════════════════════════════
class Tenant(Base):
    """Un record per negozio, dal momento dell'invito.

    `idx` e `db_uri_enc` restano NULL finche' il tenant non viene creato
    davvero: il provisioning avviene dopo firma e incasso, perche' un
    database creato per una trattativa non chiusa consuma connessioni.
    """
    __tablename__ = 'tenant'

    id             = Column(Integer, primary_key=True, autoincrement=True)
    idx            = Column(Integer, unique=True)      # indice /s/<idx> in wsgi.py
    db_uri_enc     = Column(Text)                      # cifrata, mai in chiaro
    business_name  = Column(String(150), nullable=False)
    status         = Column(String(20), nullable=False, default='invited',
                            server_default='invited')
    created_at     = Column(DateTime(timezone=True), nullable=False,
                            server_default=func.now())
    provisioned_at = Column(DateTime(timezone=True))
    # Data di cessazione del rapporto. Fa partire i 30 giorni dell'art. 20.1.c,
    # scaduti i quali i dati vanno cancellati: il pannello owner lo ricorda,
    # la cancellazione e' manuale.
    terminated_at  = Column(DateTime(timezone=True))
    # Valorizzata quando la cancellazione e' stata eseguita davvero: serve a
    # far sparire l'avviso e a poter dimostrare QUANDO si e' cancellato.
    purged_at      = Column(DateTime(timezone=True))

    __table_args__ = (
        CheckConstraint(
            "status IN ('invited','signed','provisioning','active',"
            "'suspended','terminated')",
            name='tenant_status_ck'),
    )

    def __repr__(self):
        return f"<Tenant {self.id} {self.business_name!r} {self.status}>"


class OnboardingInvite(Base):
    """Link monouso di attivazione.

    Il token in chiaro vive solo dentro il link consegnato al cliente: qui se
    ne conserva lo SHA-256, cosi' chi legge il database non puo' usarlo.
    """
    __tablename__ = 'onboarding_invite'

    id         = Column(Integer, primary_key=True, autoincrement=True)
    tenant_id  = Column(Integer, ForeignKey('tenant.id', ondelete='CASCADE'),
                        nullable=False, index=True)
    token_hash = Column(String(64), nullable=False, unique=True)
    email      = Column(String(120))
    expires_at = Column(DateTime(timezone=True), nullable=False)
    opened_at  = Column(DateTime(timezone=True))
    used_at    = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), nullable=False,
                        server_default=func.now())


# ═══════════════════════════════════════════════════════════════════════
#  CONTRATTO
# ═══════════════════════════════════════════════════════════════════════
class Contract(Base):
    """Dati raccolti dal form di attivazione.

    E' la fonte di verita': al provisioning le colonne anagrafiche vengono
    copiate in `business_info` del tenant appena creato, e i flag `module_*`
    diventano quelli di `OWNER`.
    """
    __tablename__ = 'contract'

    id               = Column(Integer, primary_key=True, autoincrement=True)
    tenant_id        = Column(Integer, ForeignKey('tenant.id', ondelete='CASCADE'),
                              nullable=False, index=True)
    status           = Column(String(20), nullable=False, default='draft',
                              server_default='draft')
    contract_version = Column(String(20))

    # anagrafica
    legal_business_name = Column(String(150))
    trade_name          = Column(String(150))
    legal_form          = Column(String(50))
    vat_number          = Column(String(20))
    fiscal_code         = Column(String(16))
    rea_number          = Column(String(20))
    rea_province        = Column(String(2))
    pec                 = Column(String(120))
    sdi_code            = Column(String(7))

    # sede legale
    legal_address  = Column(String(200))
    legal_cap      = Column(String(10))
    legal_city     = Column(String(100))
    legal_province = Column(String(2))

    # sede operativa: e' questa che finisce in business_info
    op_same_as_legal = Column(Boolean, default=True, server_default='true')
    op_address       = Column(String(200))
    op_cap           = Column(String(10))
    op_city          = Column(String(100))
    op_province      = Column(String(2))

    # contatti
    email   = Column(String(120))
    phone   = Column(String(30))
    mobile  = Column(String(30))
    website = Column(String(200))

    # firmatario
    signer_first_name  = Column(String(80))
    signer_last_name   = Column(String(80))
    signer_fiscal_code = Column(String(16))
    signer_role        = Column(String(50))
    signer_mobile      = Column(String(30))   # utenza per l'OTP
    signer_email       = Column(String(120))

    # pre-configurazione dell'istanza.
    # opening_time e closing_time sono NOT NULL in business_info e non hanno
    # default: chiederli qui evita il 9:00-19:00 inventato dal provisioning.
    opening_time        = Column(Time)
    closing_time        = Column(Time)
    closing_days        = Column(Text)        # JSON, stesso formato del tenant
    vat_percentage      = Column(Numeric(5, 2), default=22.0, server_default='22.0')
    operators_count     = Column(Integer)
    printer_model       = Column(String(30))
    current_software    = Column(String(100))
    has_data_to_migrate = Column(Boolean)

    # moduli sottoscritti -> flag di OWNER nel tenant
    module_base      = Column(Boolean, default=True,  server_default='true')
    module_web       = Column(Boolean, default=False, server_default='false')
    module_pacchetti = Column(Boolean, default=False, server_default='false')
    module_solarium  = Column(Boolean, default=False, server_default='false')

    # condizioni economiche, impostate dall'owner all'invito e mostrate in
    # sola lettura al cliente: non e' il cliente a scegliersi il prezzo
    starter_total       = Column(Numeric(10, 2))
    saas_monthly_amount = Column(Numeric(10, 2))
    # Listino: 'standard' (39/mese) | 'premium' (59/mese) | 'custom'.
    # Su 'custom' la motivazione e' OBBLIGATORIA e imposta lato server: un
    # prezzo fuori listino senza una ragione scritta, fra due anni, non se lo
    # ricorda nessuno — e in caso di contestazione non e' difendibile.
    price_plan          = Column(String(20))
    price_note          = Column(Text)

    # SEPA: mai l'IBAN completo in chiaro, solo il riferimento del mandato
    sepa_mandate_ref = Column(String(64))
    sepa_iban_last4  = Column(String(4))
    sepa_signed_at   = Column(DateTime(timezone=True))

    created_at = Column(DateTime(timezone=True), nullable=False,
                        server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False,
                        server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        CheckConstraint("status IN ('draft','ready','signed','void')",
                        name='contract_status_ck'),
    )

    def __repr__(self):
        return f"<Contract {self.id} {self.legal_business_name!r} {self.status}>"


class ContractConsent(Base):
    """Una riga per spunta accettata.

    Le clausole ex artt. 1341-1342 c.c. richiedono un'accettazione SEPARATA e
    successiva a quella del contratto: per questo sono righe distinte e non un
    unico booleano. Di ognuna si conserva versione e impronta del documento
    accettato, perche' il testo cambia nel tempo.
    """
    __tablename__ = 'contract_consent'

    id          = Column(Integer, primary_key=True, autoincrement=True)
    contract_id = Column(Integer, ForeignKey('contract.id', ondelete='CASCADE'),
                         nullable=False, index=True)
    kind        = Column(String(40), nullable=False)
    accepted    = Column(Boolean, nullable=False)
    doc_version = Column(String(20))
    doc_sha256  = Column(String(64))
    accepted_at = Column(DateTime(timezone=True), nullable=False,
                         server_default=func.now())
    ip          = Column(String(45))
    user_agent  = Column(Text)

    __table_args__ = (
        CheckConstraint(
            "kind IN ('contract','art1341','dpa','remote_support','not_consumer')",
            name='contract_consent_kind_ck'),
    )


class ContractSignature(Base):
    """Firma e prove.

    `pdf_bytes` e' la copia autorevole: il contratto va conservato 10 anni
    (art. 2220 c.c.) e non puo' vivere solo nel database del tenant, che viene
    dismesso alla cessazione del rapporto. I due binari sono `deferred` cosi'
    non vengono caricati a ogni query sull'elenco delle pratiche.
    """
    __tablename__ = 'contract_signature'

    id                = Column(Integer, primary_key=True, autoincrement=True)
    contract_id       = Column(Integer, ForeignKey('contract.id', ondelete='CASCADE'),
                               nullable=False, index=True)
    method            = Column(String(30), nullable=False)   # coupon_infocert | certyneo_aes | otp_interno
    provider          = Column(String(50))
    provider_envelope = Column(String(120))
    signed_at         = Column(DateTime(timezone=True))
    ip                = Column(String(45))
    user_agent        = Column(Text)
    pdf_sha256        = Column(String(64), nullable=False)
    pdf_bytes         = deferred(Column(LargeBinary))
    audit_pdf_bytes   = deferred(Column(LargeBinary))
    audit_json        = Column(JSONB)
    created_at        = Column(DateTime(timezone=True), nullable=False,
                               server_default=func.now())


# ═══════════════════════════════════════════════════════════════════════
#  FATTURAZIONE — sostituisce owner_billing.json
# ═══════════════════════════════════════════════════════════════════════
class Billing(Base):
    """Stessi campi del JSON, cosi' `_compliance_status()` di wsgi.py
    continua a funzionare senza riscriverne la logica."""
    __tablename__ = 'billing'

    tenant_id           = Column(Integer, ForeignKey('tenant.id', ondelete='CASCADE'),
                                 primary_key=True)
    activation_date     = Column(Date)
    contract_start_date = Column(Date)
    starter_expiry_date = Column(Date)
    starter_total       = Column(Numeric(10, 2))
    saas_monthly_amount = Column(Numeric(10, 2))
    saas_next_renewal   = Column(Date)
    max_payment_days    = Column(Integer, nullable=False, default=15, server_default='15')
    is_owner_db         = Column(Boolean, nullable=False, default=False,
                                 server_default='false')
    # Riferimenti presso i fornitori esterni. I nomi sono volutamente NEUTRI:
    # il fornitore di fatturazione elettronica (oggi OpenAPI) e quello dei
    # pagamenti (Stripe/PayPal) possono cambiare senza rinominare le colonne.
    # Non si usa "openapi_*" anche perche' collide con lo standard OpenAPI.
    einvoice_customer_id = Column(String(64))
    payment_customer_ref = Column(String(64))
    updated_at          = Column(DateTime(timezone=True), nullable=False,
                                 server_default=func.now(), onupdate=func.now())


# I nomi delle colonne di Invoice e Payment ricalcano ESATTAMENTE le chiavi
# dei dizionari gia' usati dalle rotte /owner-setup/billing/* in wsgi.py. E'
# voluto: cosi' la conversione dict <-> riga e' meccanica e non c'e' un
# glossario da ricordare. Anche l'id resta quello generato dal codice
# (uuid4().hex[:10]) invece di un serial, perche' il front-end lo usa gia'
# per identificare la riga da cancellare o da segnare come pagata.
class Invoice(Base):
    __tablename__ = 'invoice'

    id           = Column(String(32), primary_key=True)
    tenant_id    = Column(Integer, ForeignKey('tenant.id', ondelete='CASCADE'),
                          nullable=False, index=True)
    date         = Column(Date)
    number       = Column(String(50))
    description  = Column(Text)
    amount       = Column(Numeric(10, 2), nullable=False, default=0, server_default='0')
    paid         = Column(Boolean, nullable=False, default=False, server_default='false')
    einvoice_id  = Column(String(64))   # id della fattura presso il provider
    einvoice_url = Column(Text)         # link al PDF/XML presso il provider
    created_at   = Column(DateTime(timezone=True), nullable=False,
                          server_default=func.now())


class Payment(Base):
    __tablename__ = 'payment'

    id         = Column(String(32), primary_key=True)
    tenant_id  = Column(Integer, ForeignKey('tenant.id', ondelete='CASCADE'),
                        nullable=False, index=True)
    date       = Column(Date)
    amount     = Column(Numeric(10, 2), nullable=False, default=0, server_default='0')
    method     = Column(String(40))
    reference  = Column(String(120))
    provider_payment_id = Column(String(64))   # id dell'incasso presso il provider
    created_at = Column(DateTime(timezone=True), nullable=False,
                        server_default=func.now())
