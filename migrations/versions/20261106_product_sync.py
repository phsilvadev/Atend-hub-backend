"""Tenant product catalog and staged imports."""
from alembic import op
import sqlalchemy as sa
revision = '20261106_product_sync'
down_revision = '20261106_gestaoclick_access'
branch_labels = None
depends_on = None

def upgrade():
    op.create_table('products',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('company_id', sa.String(36), sa.ForeignKey('companies.id'), nullable=False),
        sa.Column('erp_id', sa.String(40), nullable=False),
        sa.Column('code', sa.String(160), nullable=False),
        sa.Column('name', sa.String(500), nullable=False),
        sa.Column('description', sa.Text(), nullable=False),
        sa.Column('category', sa.String(500), nullable=False),
        sa.Column('active', sa.Boolean(), nullable=False),
        sa.Column('has_variations', sa.Boolean(), nullable=False),
        sa.Column('synced_at', sa.Integer(), nullable=False),
        sa.UniqueConstraint('company_id', 'erp_id'))
    op.create_index('ix_products_company_id', 'products', ['company_id'])
    op.create_table('product_syncs',
        sa.Column('company_id', sa.String(36), sa.ForeignKey('companies.id'), primary_key=True),
        sa.Column('run_id', sa.String(36), nullable=False),
        sa.Column('credential_version', sa.Integer(), nullable=False),
        sa.Column('store_id', sa.String(40), nullable=False),
        sa.Column('status', sa.String(16), nullable=False),
        sa.Column('next_page', sa.Integer(), nullable=False),
        sa.Column('total_pages', sa.Integer(), nullable=True),
        sa.Column('processed', sa.Integer(), nullable=False),
        sa.Column('started_at', sa.Integer(), nullable=False),
        sa.Column('completed_at', sa.Integer(), nullable=True),
        sa.Column('last_success_at', sa.Integer(), nullable=True),
        sa.Column('error_code', sa.String(40), nullable=True),
        sa.Column('lease_until', sa.Integer(), nullable=True))
    op.create_table('product_sync_items',
        sa.Column('company_id', sa.String(36), sa.ForeignKey('companies.id'), primary_key=True),
        sa.Column('erp_id', sa.String(40), primary_key=True),
        sa.Column('data', sa.JSON(), nullable=False))

def downgrade():
    op.drop_table('product_sync_items')
    op.drop_table('product_syncs')
    op.drop_index('ix_products_company_id', table_name='products')
    op.drop_table('products')
