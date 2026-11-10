"""Isolated support history, single-flight threads and daily reservations."""
from alembic import op
import sqlalchemy as sa
revision='20261110_support'
down_revision='20261110_platform_settings'
branch_labels=None
depends_on=None

def upgrade():
    op.create_table('support_threads',sa.Column('company_id',sa.String(36),primary_key=True),sa.Column('user_id',sa.String(36),primary_key=True),sa.Column('pending_id',sa.String(36),nullable=True),sa.Column('pending_at',sa.Integer(),nullable=False),sa.Column('sequence',sa.Integer(),nullable=False),sa.ForeignKeyConstraint(['user_id','company_id'],['users.id','users.company_id']))
    op.create_table('support_turns',sa.Column('id',sa.String(36),primary_key=True),sa.Column('company_id',sa.String(36),nullable=False),sa.Column('user_id',sa.String(36),nullable=False),sa.Column('request_id',sa.String(36),nullable=False),sa.Column('sequence',sa.Integer(),nullable=False),sa.Column('question',sa.Text(),nullable=False),sa.Column('answer',sa.Text(),nullable=True),sa.Column('status',sa.String(20),nullable=False),sa.Column('error_code',sa.String(30),nullable=True),sa.Column('model',sa.String(120),nullable=False),sa.Column('config_version',sa.Integer(),nullable=False),sa.Column('input_tokens',sa.Integer(),nullable=True),sa.Column('output_tokens',sa.Integer(),nullable=True),sa.Column('sources',sa.JSON(),nullable=False),sa.Column('created_at',sa.Integer(),nullable=False),sa.UniqueConstraint('company_id','user_id','request_id',name='uq_support_request'),sa.ForeignKeyConstraint(['user_id','company_id'],['users.id','users.company_id']))
    for col in ['company_id','user_id','created_at']:op.create_index('ix_support_turns_'+col,'support_turns',[col])
    op.create_table('support_quotas',sa.Column('scope',sa.String(120),primary_key=True),sa.Column('day',sa.Integer(),primary_key=True),sa.Column('used',sa.Integer(),nullable=False))

def downgrade():
    op.drop_table('support_quotas');op.drop_table('support_turns');op.drop_table('support_threads')
