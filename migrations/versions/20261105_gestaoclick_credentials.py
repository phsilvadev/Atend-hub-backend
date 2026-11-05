"""GestaoClick credentials only; no ERP transport or synchronization."""
from alembic import op
import sqlalchemy as sa
revision='20261105_gestaoclick_credentials'
down_revision='20261105_whatsapp_official'
branch_labels=None
depends_on=None

def upgrade():
    op.create_table('gestaoclick_connections',
        sa.Column('company_id',sa.String(36),sa.ForeignKey('companies.id'),primary_key=True),
        sa.Column('base_url',sa.String(300),nullable=False),
        sa.Column('encrypted_credentials',sa.Text(),nullable=True),
        sa.Column('version',sa.Integer(),nullable=False),
        sa.Column('updated_at',sa.Integer(),nullable=False))

def downgrade():
    op.drop_table('gestaoclick_connections')
