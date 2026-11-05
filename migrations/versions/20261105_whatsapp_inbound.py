"""Tenant WhatsApp routing and atomic inbound deduplication."""
from alembic import op
import sqlalchemy as sa
revision = '20261105_whatsapp_inbound'
down_revision = '20261105_shared_knowledge'
branch_labels = None
depends_on = None

def upgrade():
    op.create_table('whatsapp_numbers',
        sa.Column('phone_number_id',sa.String(40),primary_key=True),
        sa.Column('company_id',sa.String(36),sa.ForeignKey('companies.id'),nullable=False),
        sa.Column('waba_id',sa.String(40),nullable=False),
        sa.Column('active',sa.Boolean(),nullable=False),
        sa.Column('revision',sa.Integer(),nullable=False))
    op.create_index('ix_whatsapp_numbers_company_id','whatsapp_numbers',['company_id'])
    op.create_table('whatsapp_receipts',
        sa.Column('phone_number_id',sa.String(40),sa.ForeignKey('whatsapp_numbers.phone_number_id'),primary_key=True),
        sa.Column('external_id',sa.String(200),primary_key=True),
        sa.Column('message_id',sa.Integer(),sa.ForeignKey('conversation_messages.id'),nullable=False),
        sa.Column('received_at',sa.Integer(),nullable=False))

def downgrade():
    op.drop_table('whatsapp_receipts')
    op.drop_index('ix_whatsapp_numbers_company_id',table_name='whatsapp_numbers')
    op.drop_table('whatsapp_numbers')
