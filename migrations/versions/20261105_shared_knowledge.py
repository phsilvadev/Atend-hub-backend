"""Separate platform identity and reviewed shared sector knowledge."""
from alembic import op
import sqlalchemy as sa
revision='20261105_shared_knowledge'
down_revision='20261105_conversation_reads'
branch_labels=None
depends_on=None

def upgrade():
    op.create_table('platform_admins',sa.Column('id',sa.String(36),primary_key=True),sa.Column('name',sa.String(120),nullable=False),sa.Column('email',sa.String(254),nullable=False,unique=True),sa.Column('password_hash',sa.String(512),nullable=False),sa.Column('active',sa.Boolean(),nullable=False))
    op.create_table('platform_sessions',sa.Column('token_hash',sa.String(64),primary_key=True),sa.Column('admin_id',sa.String(36),sa.ForeignKey('platform_admins.id'),nullable=False),sa.Column('expires_at',sa.Integer(),nullable=False),sa.Column('revoked',sa.Boolean(),nullable=False))
    op.create_index('ix_platform_sessions_admin_id','platform_sessions',['admin_id'])
    op.create_table('platform_audit',sa.Column('id',sa.String(36),primary_key=True),sa.Column('admin_id',sa.String(36),sa.ForeignKey('platform_admins.id'),nullable=False),sa.Column('action',sa.String(80),nullable=False),sa.Column('target_id',sa.String(36),nullable=True),sa.Column('created_at',sa.Integer(),nullable=False))
    op.create_table('knowledge_imports',sa.Column('id',sa.String(36),primary_key=True),sa.Column('admin_id',sa.String(36),sa.ForeignKey('platform_admins.id'),nullable=False),sa.Column('request_id',sa.String(36),nullable=False),sa.Column('request_hash',sa.String(64),nullable=False),sa.Column('authorization_reference',sa.String(500),nullable=False),sa.Column('sanitized_messages',sa.JSON(),nullable=False),sa.Column('redactions',sa.Integer(),nullable=False),sa.Column('created_at',sa.Integer(),nullable=False),sa.UniqueConstraint('admin_id','request_id',name='uq_knowledge_import_request'))
    op.create_table('knowledge_entries',sa.Column('id',sa.String(36),primary_key=True),sa.Column('import_id',sa.String(36),sa.ForeignKey('knowledge_imports.id'),nullable=True),sa.Column('version',sa.Integer(),nullable=False),sa.Column('current_revision',sa.Integer(),nullable=False),sa.Column('published_revision',sa.Integer(),nullable=True),sa.Column('active',sa.Boolean(),nullable=False),sa.Column('created_at',sa.Integer(),nullable=False))
    op.create_table('knowledge_revisions',sa.Column('entry_id',sa.String(36),sa.ForeignKey('knowledge_entries.id'),primary_key=True),sa.Column('revision',sa.Integer(),primary_key=True),sa.Column('title',sa.String(180),nullable=False),sa.Column('body',sa.Text(),nullable=False),sa.Column('kind',sa.String(30),nullable=False),sa.Column('source_reference',sa.String(1000),nullable=False),sa.Column('category',sa.String(80),nullable=False),sa.Column('admin_id',sa.String(36),sa.ForeignKey('platform_admins.id'),nullable=False),sa.Column('created_at',sa.Integer(),nullable=False))
    op.create_table('knowledge_approvals',sa.Column('id',sa.String(36),primary_key=True),sa.Column('entry_id',sa.String(36),sa.ForeignKey('knowledge_entries.id'),nullable=False),sa.Column('revision',sa.Integer(),nullable=False),sa.Column('admin_id',sa.String(36),sa.ForeignKey('platform_admins.id'),nullable=False),sa.Column('review_note',sa.String(1000),nullable=False),sa.Column('created_at',sa.Integer(),nullable=False))

def downgrade():
    for table in ['knowledge_approvals','knowledge_revisions','knowledge_entries','knowledge_imports','platform_audit','platform_sessions','platform_admins']:
        op.drop_table(table)
