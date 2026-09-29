"""feed hub v2: mappings, merge rules, product fields (tz spec)

Revision ID: a7d2e9f4c1b8
Revises: f8c2d4a9e1b3
Create Date: 2026-09-29

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = 'a7d2e9f4c1b8'
down_revision = 'f8c2d4a9e1b3'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('feed_sources', sa.Column('last_etag', sa.Text(), nullable=True))
    op.add_column('feed_sources', sa.Column('last_modified', sa.Text(), nullable=True))
    op.add_column('feed_sources', sa.Column('last_hash', sa.Text(), nullable=True))
    op.add_column('feed_sources', sa.Column('status', sa.String(length=20), nullable=True))
    op.add_column('products', sa.Column('gtin', sa.Text(), nullable=True))
    op.add_column('products', sa.Column('vendor_code', sa.Text(), nullable=True))
    op.add_column('products', sa.Column('title', sa.Text(), nullable=True))
    op.add_column('products', sa.Column('description', sa.Text(), nullable=True))
    op.add_column('products', sa.Column('images', postgresql.JSONB(astext_type=sa.Text()),
                                        nullable=False, server_default='[]'))
    op.add_column('products', sa.Column('merged_from', postgresql.JSONB(astext_type=sa.Text()),
                                        nullable=False, server_default='{}'))
    op.add_column('feed_runs', sa.Column('error_text', sa.Text(), nullable=True))
    op.create_table(
        'feed_mappings',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('tenant_id', sa.UUID(), nullable=False),
        sa.Column('source_id', sa.UUID(), nullable=True),
        sa.Column('template_for', sa.String(length=20), nullable=True),
        sa.Column('xml_path', sa.Text(), nullable=False),
        sa.Column('crm_field', sa.String(length=64), nullable=False),
        sa.Column('transform', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['source_id'], ['feed_sources.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_table(
        'merge_rules',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('tenant_id', sa.UUID(), nullable=False),
        sa.Column('field', sa.String(length=64), nullable=False),
        sa.Column('strategy', sa.String(length=20), nullable=False),
        sa.Column('source_order', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )


def downgrade() -> None:
    op.drop_table('merge_rules')
    op.drop_table('feed_mappings')
    op.drop_column('feed_runs', 'error_text')
    op.drop_column('products', 'merged_from')
    op.drop_column('products', 'images')
    op.drop_column('products', 'description')
    op.drop_column('products', 'title')
    op.drop_column('products', 'vendor_code')
    op.drop_column('products', 'gtin')
    op.drop_column('feed_sources', 'status')
    op.drop_column('feed_sources', 'last_hash')
    op.drop_column('feed_sources', 'last_modified')
    op.drop_column('feed_sources', 'last_etag')
