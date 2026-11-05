"""Per-user read cursors and manual handling times."""
from alembic import op
import sqlalchemy as sa
revision = '20261105_conversation_reads'
down_revision = '20261105_manual_conversations'
branch_labels = None
depends_on = None

def upgrade():
    op.add_column('conversations', sa.Column('first_response_at', sa.Integer(), nullable=True))
    op.add_column('conversations', sa.Column('handling_seconds', sa.Integer(), nullable=False, server_default='0'))
    op.add_column('conversations', sa.Column('opened_at', sa.Integer(), nullable=True))
    op.execute(sa.text("UPDATE conversations SET first_response_at = (SELECT MIN(created_at) FROM conversation_messages WHERE conversation_id = conversations.id AND company_id = conversations.company_id AND kind = 'manual_outbound'), handling_seconds = CASE WHEN status IN ('closed','converted') THEN CASE WHEN COALESCE(closed_at, updated_at) > created_at THEN COALESCE(closed_at, updated_at) - created_at ELSE 0 END ELSE 0 END, opened_at = CASE WHEN status NOT IN ('closed','converted') THEN created_at ELSE NULL END"))
    op.create_table('conversation_reads',
        sa.Column('company_id',sa.String(36),sa.ForeignKey('companies.id'),primary_key=True),
        sa.Column('conversation_id',sa.String(36),primary_key=True),
        sa.Column('user_id',sa.String(36),primary_key=True),
        sa.Column('last_message_id',sa.Integer(),nullable=False),
        sa.Column('read_at',sa.Integer(),nullable=False),
        sa.ForeignKeyConstraint(['conversation_id','company_id'],['conversations.id','conversations.company_id']),
        sa.ForeignKeyConstraint(['user_id','company_id'],['users.id','users.company_id']))

def downgrade():
    op.drop_table('conversation_reads')
    op.drop_column('conversations', 'opened_at')
    op.drop_column('conversations', 'handling_seconds')
    op.drop_column('conversations', 'first_response_at')
