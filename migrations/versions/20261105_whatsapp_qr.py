"""Non-official QR session isolated by tenant."""
from alembic import op
import sqlalchemy as sa
revision='20261105_whatsapp_qr'
down_revision='20261105_whatsapp_inbound'
branch_labels=None
depends_on=None

def upgrade():
    op.create_table('whatsapp_qr_connections',
        sa.Column('company_id',sa.String(36),sa.ForeignKey('companies.id'),primary_key=True),
        sa.Column('session_id',sa.String(36),nullable=False,unique=True),
        sa.Column('active',sa.Boolean(),nullable=False))

def downgrade():
    op.drop_table('whatsapp_qr_connections')
