"""Google identities, browser-bound nonce flows and password reset fingerprints."""
from alembic import op
import sqlalchemy as sa
revision = '20261109_client_auth'
down_revision = '20261106_meta_signup'
branch_labels = None
depends_on = None

def upgrade():
    op.create_table('google_identities', sa.Column('subject', sa.String(255), primary_key=True), sa.Column('user_id', sa.String(36), sa.ForeignKey('users.id'), unique=True, nullable=False))
    op.create_table('google_auth_flows', sa.Column('state_hash', sa.String(64), primary_key=True), sa.Column('browser_hash', sa.String(64), nullable=False), sa.Column('nonce_hash', sa.String(64), nullable=False), sa.Column('mode', sa.String(10), nullable=False), sa.Column('expires_at', sa.Integer(), nullable=False), sa.Column('consumed', sa.Boolean(), nullable=False))
    op.create_index('ix_google_auth_flows_expires_at', 'google_auth_flows', ['expires_at'])
    op.create_table('password_resets', sa.Column('token_hash', sa.String(64), primary_key=True), sa.Column('user_id', sa.String(36), sa.ForeignKey('users.id'), nullable=False), sa.Column('password_version', sa.String(64), nullable=False), sa.Column('expires_at', sa.Integer(), nullable=False), sa.Column('consumed', sa.Boolean(), nullable=False))
    op.create_index('ix_password_resets_user_id', 'password_resets', ['user_id'])
    op.create_index('ix_password_resets_expires_at', 'password_resets', ['expires_at'])

def downgrade():
    op.drop_table('password_resets')
    op.drop_table('google_auth_flows')
    op.drop_table('google_identities')
