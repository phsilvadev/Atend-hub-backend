"""Persistent single-use anti-bot challenge fingerprints."""
from alembic import op
import sqlalchemy as sa
revision = '20261106_turnstile'
down_revision = '20261106_product_images'
branch_labels = None
depends_on = None

def upgrade():
    op.create_table('challenge_uses', sa.Column('token_hash', sa.String(64), primary_key=True), sa.Column('expires_at', sa.Integer(), nullable=False))
    op.create_index('ix_challenge_uses_expires_at', 'challenge_uses', ['expires_at'])

def downgrade():
    op.drop_index('ix_challenge_uses_expires_at', table_name='challenge_uses')
    op.drop_table('challenge_uses')
