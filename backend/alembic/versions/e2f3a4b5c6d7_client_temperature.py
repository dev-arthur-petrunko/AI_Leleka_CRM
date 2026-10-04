"""client temperature: ручна гарячість клієнта (null = авто-скоринг)

Revision ID: e2f3a4b5c6d7
Revises: d1e2f3a4b5c6
Create Date: 2026-10-04

"""
from alembic import op
import sqlalchemy as sa


revision = 'e2f3a4b5c6d7'
down_revision = 'd1e2f3a4b5c6'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('clients', sa.Column('temperature', sa.String(10),
                                       nullable=True))


def downgrade() -> None:
    op.drop_column('clients', 'temperature')
