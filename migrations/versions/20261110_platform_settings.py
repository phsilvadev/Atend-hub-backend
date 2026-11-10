"""Platform primary identity, versioned administrators and encrypted OpenAI config."""
from alembic import op
import sqlalchemy as sa
revision='20261110_platform_settings'
down_revision='20261109_client_auth'
branch_labels=None
depends_on=None

def upgrade():
    op.add_column('platform_admins',sa.Column('version',sa.Integer(),nullable=False,server_default='1'))
    op.create_table('platform_control',sa.Column('id',sa.Integer(),primary_key=True),sa.Column('primary_admin_id',sa.String(36),sa.ForeignKey('platform_admins.id'),nullable=True),sa.Column('version',sa.Integer(),nullable=False))
    connection=op.get_bind()
    ids=list(connection.execute(sa.text('SELECT id FROM platform_admins')).scalars())
    primary=ids[0] if len(ids)==1 else None
    if len(ids)>1:
        rows=connection.execute(sa.text("SELECT admin_id, MIN(created_at) AS first_at FROM platform_audit WHERE action='platform.admin.created' GROUP BY admin_id ORDER BY first_at")).all()
        if not rows or (len(rows)>1 and rows[0].first_at==rows[1].first_at):
            raise RuntimeError('Identidade primária ambígua. Defina a migração de identidade antes de prosseguir.')
        primary=rows[0].admin_id
    connection.execute(sa.text('INSERT INTO platform_control (id,primary_admin_id,version) VALUES (1,:primary,1)'),{'primary':primary})
    op.create_table('platform_openai',sa.Column('id',sa.Integer(),primary_key=True),sa.Column('key_ciphertext',sa.Text(),nullable=True),sa.Column('model',sa.String(120),nullable=False),sa.Column('version',sa.Integer(),nullable=False),sa.Column('checked_at',sa.Integer(),nullable=True),sa.Column('check_status',sa.String(30),nullable=True))
    connection.execute(sa.text("INSERT INTO platform_openai (id,model,version) VALUES (1,'gpt-4.1-mini',1)"))

def downgrade():
    op.drop_table('platform_openai')
    op.drop_table('platform_control')
    op.drop_column('platform_admins','version')
