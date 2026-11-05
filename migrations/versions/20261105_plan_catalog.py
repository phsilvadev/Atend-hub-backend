"""Plan catalog; no commercial or demo data inserted by migrations."""
from alembic import op
import sqlalchemy as sa
revision = '20261105_plan_catalog'
down_revision = '20261105_company_profile'
branch_labels = None
depends_on = None

def upgrade():
    op.create_table('plans',
        sa.Column('code', sa.String(40), primary_key=True),
        sa.Column('name', sa.String(80), nullable=False),
        sa.Column('description', sa.String(240), nullable=False),
        sa.Column('monthly_price_cents', sa.Integer(), nullable=False),
        sa.Column('currency', sa.String(3), nullable=False),
        sa.Column('user_limit', sa.Integer(), nullable=False),
        sa.Column('features', sa.JSON(), nullable=False),
        sa.Column('sort_order', sa.Integer(), nullable=False),
        sa.Column('active', sa.Boolean(), nullable=False),
        sa.Column('is_demo', sa.Boolean(), nullable=False),
        sa.CheckConstraint('monthly_price_cents >= 0', name='ck_plan_price'),
        sa.CheckConstraint('user_limit > 0', name='ck_plan_user_limit'))

def downgrade():
    op.drop_table('plans')
