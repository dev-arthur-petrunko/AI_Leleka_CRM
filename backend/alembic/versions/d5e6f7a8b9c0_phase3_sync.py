"""phase 3 sync: sync_state, lead_forms, integration health

Revision ID: d5e6f7a8b9c0
Revises: c9d4e5f6a7b8
Create Date: 2026-09-30

"""
import sqlalchemy as sa
from alembic import op

revision = 'd5e6f7a8b9c0'
down_revision = 'c9d4e5f6a7b8'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('integrations', sa.Column('status', sa.String(20),
                                           nullable=False, server_default='ok'))
    op.add_column('integrations', sa.Column('last_error', sa.Text(), nullable=True))
    op.create_table(
        'sync_state',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('tenant_id', sa.UUID(), sa.ForeignKey('tenants.id', ondelete='CASCADE'),
                  nullable=False),
        sa.Column('integration_id', sa.UUID(), sa.ForeignKey('integrations.id', ondelete='CASCADE'),
                  nullable=False),
        sa.Column('cursor', sa.Text(), nullable=True),
        sa.Column('last_success_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('last_error', sa.Text(), nullable=True),
        sa.Column('consecutive_failures', sa.Integer(), nullable=False, server_default='0'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('tenant_id', 'integration_id'),
    )
    op.create_table(
        'lead_forms',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('tenant_id', sa.UUID(), sa.ForeignKey('tenants.id', ondelete='CASCADE'),
                  nullable=False),
        sa.Column('name', sa.Text(), nullable=False),
        sa.Column('secret', sa.Text(), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )


def downgrade() -> None:
    op.drop_table('lead_forms')
    op.drop_table('sync_state')
    op.drop_column('integrations', 'last_error')
    op.drop_column('integrations', 'status')
