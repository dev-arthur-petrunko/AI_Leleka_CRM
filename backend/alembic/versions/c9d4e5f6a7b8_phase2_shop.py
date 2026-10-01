"""phase 2 shop: orders, phones index, tags, custom, pipelines

Revision ID: c9d4e5f6a7b8
Revises: b4e8f1a2c3d4
Create Date: 2026-09-30

"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = 'c9d4e5f6a7b8'
down_revision = 'b4e8f1a2c3d4'
branch_labels = None
depends_on = None

TABLES = ("orders", "order_items", "payments", "shipments", "returns",
          "order_status_history", "tags", "entity_tags", "custom_fields",
          "pipelines", "pipeline_stages")


def _uuid():
    return sa.Column('id', sa.UUID(), nullable=False)


def _tenant(nullable=False):
    return sa.Column('tenant_id', sa.UUID(),
                     sa.ForeignKey('tenants.id', ondelete='CASCADE'),
                     nullable=nullable)


def upgrade() -> None:
    op.add_column('clients', sa.Column('custom', postgresql.JSONB(astext_type=sa.Text()),
                                      nullable=False, server_default='{}'))
    op.create_index('ix_clients_tenant_phone', 'clients', ['tenant_id', 'phone'])

    op.create_table(
        'orders', _uuid(), _tenant(),
        sa.Column('client_id', sa.UUID(), sa.ForeignKey('clients.id', ondelete='SET NULL'), nullable=True),
        sa.Column('deal_id', sa.UUID(), sa.ForeignKey('deals.id', ondelete='SET NULL'), nullable=True),
        sa.Column('source', sa.String(20), nullable=False),
        sa.Column('external_id', sa.Text(), nullable=False),
        sa.Column('order_number', sa.Text(), nullable=True),
        sa.Column('status', sa.String(20), nullable=False, server_default='new'),
        sa.Column('payment_status', sa.String(20), nullable=False, server_default='unpaid'),
        sa.Column('payment_method', sa.String(20), nullable=True),
        sa.Column('currency', sa.String(8), nullable=False, server_default='UAH'),
        sa.Column('subtotal', sa.Numeric(12, 2), nullable=False, server_default='0'),
        sa.Column('discount', sa.Numeric(12, 2), nullable=False, server_default='0'),
        sa.Column('shipping_cost', sa.Numeric(12, 2), nullable=False, server_default='0'),
        sa.Column('total', sa.Numeric(12, 2), nullable=False, server_default='0'),
        sa.Column('placed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('raw', postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default='{}'),
        sa.Column('custom', postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default='{}'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('tenant_id', 'source', 'external_id'),
    )
    op.create_index('ix_orders_tenant_status', 'orders', ['tenant_id', 'status'])
    op.create_index('ix_orders_tenant_placed', 'orders', ['tenant_id', 'placed_at'])
    op.create_index('ix_orders_tenant_client', 'orders', ['tenant_id', 'client_id'])

    op.create_table(
        'order_items', _uuid(), _tenant(),
        sa.Column('order_id', sa.UUID(), sa.ForeignKey('orders.id', ondelete='CASCADE'), nullable=False),
        sa.Column('product_id', sa.UUID(), sa.ForeignKey('products.id', ondelete='SET NULL'), nullable=True),
        sa.Column('sku', sa.Text(), nullable=True),
        sa.Column('name', sa.Text(), nullable=False),
        sa.Column('qty', sa.Numeric(12, 3), nullable=False, server_default='1'),
        sa.Column('unit_price', sa.Numeric(12, 2), nullable=False, server_default='0'),
        sa.Column('discount', sa.Numeric(12, 2), nullable=False, server_default='0'),
        sa.Column('total', sa.Numeric(12, 2), nullable=False, server_default='0'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_table(
        'payments', _uuid(), _tenant(),
        sa.Column('order_id', sa.UUID(), sa.ForeignKey('orders.id', ondelete='SET NULL'), nullable=True),
        sa.Column('provider', sa.String(32), nullable=False),
        sa.Column('external_id', sa.Text(), nullable=False),
        sa.Column('amount', sa.Numeric(12, 2), nullable=False, server_default='0'),
        sa.Column('status', sa.String(20), nullable=False, server_default='pending'),
        sa.Column('paid_at', sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('tenant_id', 'provider', 'external_id'),
    )
    op.create_table(
        'shipments', _uuid(), _tenant(),
        sa.Column('order_id', sa.UUID(), sa.ForeignKey('orders.id', ondelete='CASCADE'), nullable=False),
        sa.Column('carrier', sa.String(20), nullable=False, server_default='novaposhta'),
        sa.Column('ttn', sa.Text(), nullable=True),
        sa.Column('status', sa.String(64), nullable=True),
        sa.Column('status_code', sa.String(32), nullable=True),
        sa.Column('cod_amount', sa.Numeric(12, 2), nullable=False, server_default='0'),
        sa.Column('last_polled_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('delivered_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('returned_at', sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_table(
        'returns', _uuid(), _tenant(),
        sa.Column('order_id', sa.UUID(), sa.ForeignKey('orders.id', ondelete='CASCADE'), nullable=False),
        sa.Column('reason', sa.Text(), nullable=True),
        sa.Column('amount', sa.Numeric(12, 2), nullable=False, server_default='0'),
        sa.Column('status', sa.String(20), nullable=False, server_default='new'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_table(
        'order_status_history', _uuid(), _tenant(),
        sa.Column('order_id', sa.UUID(), sa.ForeignKey('orders.id', ondelete='CASCADE'), nullable=False),
        sa.Column('from_status', sa.String(20), nullable=True),
        sa.Column('to_status', sa.String(20), nullable=False),
        sa.Column('changed_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('source', sa.String(20), nullable=False, server_default='manager'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_table(
        'tags', _uuid(), _tenant(),
        sa.Column('name', sa.String(64), nullable=False),
        sa.Column('color', sa.String(16), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('tenant_id', 'name'),
    )
    op.create_table(
        'entity_tags', _uuid(), _tenant(),
        sa.Column('tag_id', sa.UUID(), sa.ForeignKey('tags.id', ondelete='CASCADE'), nullable=False),
        sa.Column('entity_type', sa.String(20), nullable=False),
        sa.Column('entity_id', sa.Text(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('tenant_id', 'tag_id', 'entity_type', 'entity_id'),
    )
    op.create_table(
        'custom_fields', _uuid(), _tenant(),
        sa.Column('entity', sa.String(20), nullable=False),
        sa.Column('key', sa.String(64), nullable=False),
        sa.Column('label', sa.Text(), nullable=False),
        sa.Column('ftype', sa.String(20), nullable=False, server_default='text'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('tenant_id', 'entity', 'key'),
    )
    op.create_table(
        'pipelines', _uuid(), _tenant(),
        sa.Column('name', sa.Text(), nullable=False),
        sa.Column('is_default', sa.Boolean(), nullable=False, server_default='false'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_table(
        'pipeline_stages', _uuid(), _tenant(),
        sa.Column('pipeline_id', sa.UUID(), sa.ForeignKey('pipelines.id', ondelete='CASCADE'), nullable=False),
        sa.Column('key', sa.String(32), nullable=False),
        sa.Column('name', sa.Text(), nullable=False),
        sa.Column('position', sa.Integer(), nullable=False, server_default='0'),
        sa.PrimaryKeyConstraint('id'),
    )


def downgrade() -> None:
    for t in reversed(TABLES):
        op.drop_table(t)
    op.drop_index('ix_orders_tenant_client', table_name='orders')
    op.drop_index('ix_orders_tenant_placed', table_name='orders')
    op.drop_index('ix_orders_tenant_status', table_name='orders')
    op.drop_index('ix_clients_tenant_phone', table_name='clients')
    op.drop_column('clients', 'custom')
