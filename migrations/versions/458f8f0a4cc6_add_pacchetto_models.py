"""Add Pacchetto models

Revision ID: 458f8f0a4cc6
Revises: 
Create Date: 2026-01-01 18:48:27.268078

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '458f8f0a4cc6'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('pacchetti',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('client_id', sa.Integer(), nullable=False),
    sa.Column('nome', sa.String(length=100), nullable=False),
    sa.Column('data_sottoscrizione', sa.Date(), nullable=False),
    sa.Column('note', sa.Text(), nullable=True),
    sa.Column('status', postgresql.ENUM('Preventivo', 'Attivo', 'Completato', 'Abbandonato', 'Eliminato', name='pacchetto_status_enum'), nullable=False),
    sa.Column('history', sa.Text(), nullable=True),
    sa.Column('costo_totale_lordo', sa.Numeric(precision=10, scale=2), nullable=False),
    sa.Column('costo_totale_scontato', sa.Numeric(precision=10, scale=2), nullable=True),
    sa.ForeignKeyConstraint(['client_id'], ['clienti.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('pacchetto_operator',
    sa.Column('pacchetto_id', sa.Integer(), nullable=False),
    sa.Column('operator_id', sa.Integer(), nullable=False),
    sa.ForeignKeyConstraint(['operator_id'], ['operatori.id'], ),
    sa.ForeignKeyConstraint(['pacchetto_id'], ['pacchetti.id'], ),
    sa.PrimaryKeyConstraint('pacchetto_id', 'operator_id')
    )
    op.create_table('pacchetto_pagamento_regole',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('pacchetto_id', sa.Integer(), nullable=False),
    sa.Column('formula_pagamenti', sa.Boolean(), nullable=False),
    sa.Column('numero_rate', sa.Integer(), nullable=False),
    sa.Column('descrizione', sa.String(length=255), nullable=True),
    sa.ForeignKeyConstraint(['pacchetto_id'], ['pacchetti.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('pacchetto_rate',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('pacchetto_id', sa.Integer(), nullable=False),
    sa.Column('importo', sa.Numeric(precision=10, scale=2), nullable=False),
    sa.Column('data_scadenza', sa.Date(), nullable=True),
    sa.Column('is_pagata', sa.Boolean(), nullable=True),
    sa.Column('data_pagamento', sa.DateTime(), nullable=True),
    sa.ForeignKeyConstraint(['pacchetto_id'], ['pacchetti.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('pacchetto_sconto_regole',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('pacchetto_id', sa.Integer(), nullable=False),
    sa.Column('sconto_tipo', postgresql.ENUM('Percentuale', 'Ogni_N_Omaggio', name='sconto_tipo_enum'), nullable=False),
    sa.Column('sconto_valore', sa.Numeric(precision=10, scale=2), nullable=True),
    sa.Column('omaggi_extra', sa.Integer(), nullable=True),
    sa.Column('descrizione', sa.String(length=255), nullable=True),
    sa.ForeignKeyConstraint(['pacchetto_id'], ['pacchetti.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('pacchetto_sedute',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('pacchetto_id', sa.Integer(), nullable=False),
    sa.Column('service_id', sa.Integer(), nullable=False),
    sa.Column('ordine', sa.Integer(), nullable=False),
    sa.Column('data_trattamento', sa.DateTime(), nullable=True),
    sa.Column('operatore_id', sa.Integer(), nullable=True),
    sa.Column('stato', sa.Integer(), nullable=False),
    sa.Column('nota', sa.Text(), nullable=True),
    sa.ForeignKeyConstraint(['operatore_id'], ['operatori.id'], ),
    sa.ForeignKeyConstraint(['pacchetto_id'], ['pacchetti.id'], ),
    sa.ForeignKeyConstraint(['service_id'], ['servizi.id'], ),
    sa.PrimaryKeyConstraint('id')
    )

def downgrade():
    op.drop_table('pacchetto_sedute')
    op.drop_table('pacchetto_sconto_regole')
    op.drop_table('pacchetto_rate')
    op.drop_table('pacchetto_pagamento_regole')
    op.drop_table('pacchetto_operator')
    op.drop_table('pacchetti')