"""Private tenant product images stored in Firebase Storage."""
from alembic import op
import sqlalchemy as sa
revision = '20261106_product_images'
down_revision = '20261106_product_sync'
branch_labels = None
depends_on = None

def upgrade():
    op.add_column('products', sa.Column('image_object', sa.String(500), nullable=True))
    op.add_column('products', sa.Column('image_generation', sa.String(40), nullable=True))
    op.add_column('products', sa.Column('image_version', sa.Integer(), nullable=False, server_default='0'))
    op.add_column('products', sa.Column('image_updated_at', sa.Integer(), nullable=True))

def downgrade():
    with op.batch_alter_table('products') as batch:
        for name in ['image_updated_at', 'image_version', 'image_generation', 'image_object']:
            batch.drop_column(name)
