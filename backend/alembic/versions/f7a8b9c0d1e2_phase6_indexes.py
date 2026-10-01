"""phase 6 perf indexes

Revision ID: f7a8b9c0d1e2
Revises: e6f7a8b9c0d1
Create Date: 2026-09-30

"""
from alembic import op

revision = 'f7a8b9c0d1e2'
down_revision = 'e6f7a8b9c0d1'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_index('ix_deals_tenant_activity', 'deals', ['tenant_id', 'last_activity_at'])
    op.create_index('ix_deals_tenant_stage2', 'deals', ['tenant_id', 'stage'])


def downgrade() -> None:
    op.drop_index('ix_deals_tenant_stage2', table_name='deals')
    op.drop_index('ix_deals_tenant_activity', table_name='deals')
