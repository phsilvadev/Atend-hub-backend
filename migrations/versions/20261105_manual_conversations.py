"""Tenant-scoped customers, manual conversations and history."""
from alembic import op
import sqlalchemy as sa
revision = '20261105_manual_conversations'
down_revision = '20261105_plan_catalog'
branch_labels = None
depends_on = None

def upgrade():
    op.create_table('customers',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('company_id', sa.String(36), sa.ForeignKey('companies.id'), nullable=False),
        sa.Column('name', sa.String(120), nullable=False), sa.Column('phone', sa.String(15), nullable=False),
        sa.Column('business_name', sa.String(160), nullable=False), sa.Column('created_at', sa.Integer(), nullable=False),
        sa.UniqueConstraint('id','company_id',name='uq_customer_tenant'),
        sa.UniqueConstraint('company_id','phone',name='uq_customer_phone'))
    op.create_index('ix_customers_company_id','customers',['company_id'])
    op.create_table('conversations',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('company_id', sa.String(36), sa.ForeignKey('companies.id'), nullable=False),
        sa.Column('customer_id', sa.String(36), nullable=False), sa.Column('assigned_user_id', sa.String(36), nullable=True),
        sa.Column('subject', sa.String(200), nullable=False), sa.Column('status', sa.String(30), nullable=False),
        sa.Column('channel', sa.String(20), nullable=False), sa.Column('request_id', sa.String(36), nullable=False),
        sa.Column('request_hash', sa.String(64), nullable=False), sa.Column('created_at', sa.Integer(), nullable=False),
        sa.Column('updated_at', sa.Integer(), nullable=False), sa.Column('closed_at', sa.Integer(), nullable=True),
        sa.Column('version', sa.Integer(), nullable=False),
        sa.UniqueConstraint('id','company_id',name='uq_conversation_tenant'),
        sa.UniqueConstraint('company_id','request_id',name='uq_conversation_request'),
        sa.ForeignKeyConstraint(['customer_id','company_id'],['customers.id','customers.company_id']),
        sa.ForeignKeyConstraint(['assigned_user_id','company_id'],['users.id','users.company_id']))
    op.create_index('ix_conversation_tenant_updated','conversations',['company_id','updated_at'])
    op.create_table('conversation_messages',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('company_id', sa.String(36), sa.ForeignKey('companies.id'), nullable=False),
        sa.Column('conversation_id', sa.String(36), nullable=False), sa.Column('actor_id', sa.String(36), nullable=True),
        sa.Column('kind', sa.String(30), nullable=False), sa.Column('body', sa.Text(), nullable=False),
        sa.Column('request_id', sa.String(36), nullable=True), sa.Column('created_at', sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(['conversation_id','company_id'],['conversations.id','conversations.company_id']),
        sa.ForeignKeyConstraint(['actor_id','company_id'],['users.id','users.company_id']),
        sa.UniqueConstraint('company_id','conversation_id','request_id',name='uq_message_request'))
    op.create_index('ix_message_conversation_id','conversation_messages',['company_id','conversation_id','id'])

def downgrade():
    op.drop_table('conversation_messages')
    op.drop_table('conversations')
    op.drop_table('customers')
