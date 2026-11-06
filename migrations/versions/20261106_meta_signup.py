"""Single-use, session-bound Meta Embedded Signup attempts."""
from alembic import op
import sqlalchemy as sa
revision = '20261106_meta_signup'
down_revision = '20261106_turnstile'
branch_labels = None
depends_on = None

def upgrade():
    op.create_table('whatsapp_signup_attempts',
        sa.Column('state_hash', sa.String(64), primary_key=True),
        sa.Column('company_id', sa.String(36), sa.ForeignKey('companies.id'), nullable=False),
        sa.Column('user_id', sa.String(36), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('session_id', sa.String(64), sa.ForeignKey('sessions.token_hash'), nullable=False),
        sa.Column('connection_version', sa.Integer(), nullable=False),
        sa.Column('expires_at', sa.Integer(), nullable=False),
        sa.Column('consumed', sa.Boolean(), nullable=False),
        sa.Column('code_hash', sa.String(64), unique=True, nullable=True))
    op.create_index('ix_whatsapp_signup_attempts_company_id', 'whatsapp_signup_attempts', ['company_id'])
    op.create_index('ix_whatsapp_signup_attempts_expires_at', 'whatsapp_signup_attempts', ['expires_at'])

def downgrade():
    op.drop_index('ix_whatsapp_signup_attempts_expires_at', table_name='whatsapp_signup_attempts')
    op.drop_index('ix_whatsapp_signup_attempts_company_id', table_name='whatsapp_signup_attempts')
    op.drop_table('whatsapp_signup_attempts')
