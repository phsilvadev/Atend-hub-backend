"""Persist last access check and selected store without syncing commercial records."""
from alembic import op
import sqlalchemy as sa
revision='20261106_gestaoclick_access'
down_revision='20261105_gestaoclick_credentials'
branch_labels=None
depends_on=None

def upgrade():
    op.add_column('gestaoclick_connections',sa.Column('stores',sa.JSON(),nullable=False,server_default='[]'))
    op.add_column('gestaoclick_connections',sa.Column('selected_store_id',sa.String(40),nullable=True))
    op.add_column('gestaoclick_connections',sa.Column('tested_at',sa.Integer(),nullable=True))
    op.add_column('gestaoclick_connections',sa.Column('last_test_started_at',sa.Integer(),nullable=True))
    op.add_column('gestaoclick_connections',sa.Column('test_error_code',sa.String(40),nullable=True))

def downgrade():
    for name in ['test_error_code','last_test_started_at','tested_at','selected_store_id','stores']:
        op.drop_column('gestaoclick_connections',name)
