"""Company contact, address and weekly business hours; existing tenants preserved."""
from alembic import op
import sqlalchemy as sa
revision = '20261105_company_profile'
down_revision = '9c1654c4b7c0'
branch_labels = None
depends_on = None

def upgrade():
    op.create_table('company_profiles',
        sa.Column('company_id', sa.String(36), sa.ForeignKey('companies.id'), primary_key=True),
        *[sa.Column(name, sa.String(size), nullable=False) for name, size in [
            ('legal_name',160), ('tax_id',14), ('phone',20), ('email',254),
            ('postal_code',8), ('street',160), ('number',20), ('complement',100),
            ('district',100), ('city',100), ('state',2), ('timezone',64)]],
        sa.Column('business_hours', sa.JSON(), nullable=False))

def downgrade():
    op.drop_table('company_profiles')
