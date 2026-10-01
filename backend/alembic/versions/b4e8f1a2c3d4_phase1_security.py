"""phase 1 security: webhook secrets, tenant-scoped dedup, account hardening

Revision ID: b4e8f1a2c3d4
Revises: a7d2e9f4c1b8
Create Date: 2026-09-30

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = 'b4e8f1a2c3d4'
down_revision = 'a7d2e9f4c1b8'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('integrations', sa.Column('webhook_secret', sa.Text(), nullable=True))
    op.add_column('users', sa.Column('must_change_password', sa.Boolean(),
                                     nullable=False, server_default='false'))
    op.add_column('users', sa.Column('email_confirmed', sa.Boolean(),
                                     nullable=False, server_default='false'))
    op.add_column('users', sa.Column('token_version', sa.Integer(),
                                     nullable=False, server_default='0'))
    op.add_column('users', sa.Column('totp_secret', sa.Text(), nullable=True))
    # сироти без тенанта непридатні для обробки — видаляємо, потім NOT NULL
    op.execute("DELETE FROM webhook_events WHERE tenant_id IS NULL")
    op.execute("ALTER TABLE webhook_events ALTER COLUMN tenant_id SET NOT NULL")
    # знімаємо старий unique (якщо був) і ставимо tenant-scoped
    op.execute("ALTER TABLE webhook_events DROP CONSTRAINT IF EXISTS "
               "webhook_events_provider_external_id_key")
    op.execute("ALTER TABLE webhook_events DROP CONSTRAINT IF EXISTS "
               "uq_webhook_provider_external")
    op.create_unique_constraint("uq_webhook_tenant_provider_external",
                                "webhook_events", ["tenant_id", "provider", "external_id"])
    op.create_table(
        'password_reset_tokens',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('email', sa.Text(), nullable=False),
        sa.Column('token_hash', sa.Text(), nullable=False),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('used', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('token_hash'),
    )


def downgrade() -> None:
    op.drop_table('password_reset_tokens')
    op.drop_constraint('uq_webhook_tenant_provider_external', 'webhook_events',
                       type_='unique')
    op.execute("ALTER TABLE webhook_events ALTER COLUMN tenant_id DROP NOT NULL")
    op.drop_column('users', 'totp_secret')
    op.drop_column('users', 'token_version')
    op.drop_column('users', 'email_confirmed')
    op.drop_column('users', 'must_change_password')
    op.drop_column('integrations', 'webhook_secret')
