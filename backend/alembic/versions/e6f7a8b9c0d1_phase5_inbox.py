"""phase 5 inbox + consents + telegram link

Revision ID: e6f7a8b9c0d1
Revises: d5e6f7a8b9c0
Create Date: 2026-09-30

"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = 'e6f7a8b9c0d1'
down_revision = 'd5e6f7a8b9c0'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('clients', sa.Column('consents', postgresql.JSONB(astext_type=sa.Text()),
                                      nullable=False, server_default='{}'))
    op.add_column('users', sa.Column('telegram_id', sa.Text(), nullable=True))
    op.create_table(
        'conversations',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('tenant_id', sa.UUID(), sa.ForeignKey('tenants.id', ondelete='CASCADE'),
                  nullable=False),
        sa.Column('client_id', sa.UUID(), sa.ForeignKey('clients.id', ondelete='SET NULL'),
                  nullable=True),
        sa.Column('channel', sa.String(20), nullable=False),
        sa.Column('status', sa.String(20), nullable=False, server_default='open'),
        sa.Column('assigned_to', sa.UUID(), sa.ForeignKey('users.id', ondelete='SET NULL'),
                  nullable=True),
        sa.Column('last_message_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_conv_tenant_client', 'conversations', ['tenant_id', 'client_id'])
    op.create_table(
        'messages',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('tenant_id', sa.UUID(), sa.ForeignKey('tenants.id', ondelete='CASCADE'),
                  nullable=False),
        sa.Column('conversation_id', sa.UUID(), sa.ForeignKey('conversations.id', ondelete='CASCADE'),
                  nullable=False),
        sa.Column('direction', sa.String(8), nullable=False),
        sa.Column('channel', sa.String(20), nullable=False),
        sa.Column('body', sa.Text(), nullable=False),
        sa.Column('external_id', sa.Text(), nullable=True),
        sa.Column('status', sa.String(20), nullable=False, server_default='delivered'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_msg_conv', 'messages', ['conversation_id', 'created_at'])
    op.create_table(
        'message_templates',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('tenant_id', sa.UUID(), sa.ForeignKey('tenants.id', ondelete='CASCADE'),
                  nullable=False),
        sa.Column('name', sa.Text(), nullable=False),
        sa.Column('channel', sa.String(20), nullable=False),
        sa.Column('body', sa.Text(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('tenant_id', 'name'),
    )


def downgrade() -> None:
    op.drop_table('message_templates')
    op.drop_index('ix_msg_conv', table_name='messages')
    op.drop_table('messages')
    op.drop_index('ix_conv_tenant_client', table_name='conversations')
    op.drop_table('conversations')
    op.drop_column('users', 'telegram_id')
    op.drop_column('clients', 'consents')
