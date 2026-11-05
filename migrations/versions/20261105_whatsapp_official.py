"""Encrypted per-tenant official credentials; preserve existing number routing."""
from alembic import op
import sqlalchemy as sa
revision='20261105_whatsapp_official'
down_revision='20261105_whatsapp_qr'
branch_labels=None
depends_on=None

def upgrade():
    op.create_table('whatsapp_official_connections',
        sa.Column('company_id',sa.String(36),sa.ForeignKey('companies.id'),primary_key=True),
        sa.Column('phone_number_id',sa.String(40),sa.ForeignKey('whatsapp_numbers.phone_number_id'),nullable=False,unique=True),
        sa.Column('waba_id',sa.String(40),nullable=False),
        sa.Column('encrypted_token',sa.Text(),nullable=True),
        sa.Column('display_phone_number',sa.String(40),nullable=False),
        sa.Column('verified_name',sa.String(160),nullable=False),
        sa.Column('diagnostics',sa.JSON(),nullable=False),
        sa.Column('active',sa.Boolean(),nullable=False),
        sa.Column('verified_at',sa.Integer(),nullable=False),
        sa.Column('version',sa.Integer(),nullable=False))

def downgrade():
    op.drop_table('whatsapp_official_connections')
