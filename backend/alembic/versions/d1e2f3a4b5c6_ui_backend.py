"""ui backend: preferences, convert link, saved views

Revision ID: d1e2f3a4b5c6
Revises: f7a8b9c0d1e2
Create Date: 2026-10-02

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = 'd1e2f3a4b5c6'
down_revision = 'f7a8b9c0d1e2'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('users', sa.Column('preferences', postgresql.JSONB(astext_type=sa.Text()),
                                     nullable=False, server_default='{}'))
    op.add_column('deals', sa.Column('converted_order_id', sa.UUID(),
                                     sa.ForeignKey('orders.id', ondelete='SET NULL'),
                                     nullable=True))
    op.create_table(
        'saved_views',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('tenant_id', sa.UUID(), sa.ForeignKey('tenants.id', ondelete='CASCADE'),
                  nullable=False),
        sa.Column('user_id', sa.UUID(), sa.ForeignKey('users.id', ondelete='CASCADE'),
                  nullable=True),
        sa.Column('entity', sa.String(20), nullable=False),
        sa.Column('name', sa.Text(), nullable=False),
        sa.Column('filters', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('tenant_id', 'user_id', 'entity', 'name'),
    )


def downgrade() -> None:
    op.drop_table('saved_views')
    op.drop_column('deals', 'converted_order_id')
    op.drop_column('users', 'preferences')
