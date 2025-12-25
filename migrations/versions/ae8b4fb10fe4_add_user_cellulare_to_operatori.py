from alembic import op
import sqlalchemy as sa

revision = 'ae8b4fb10fe4'
down_revision = None
branch_labels = None
depends_on = None

def upgrade():
    op.add_column(
        'operatori',
        sa.Column('user_cellulare', sa.String(), nullable=False, server_default='0')
    )

def downgrade():
    op.drop_column('operatori', 'user_cellulare')