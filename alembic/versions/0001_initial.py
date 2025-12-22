"""initial

Revision ID: 0001_initial
Revises: 
Create Date: 2025-12-22 00:00:00.000000
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '0001_initial'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'indexes',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('code', sa.String(length=64), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=True),
        sa.Column('source', sa.String(length=64), nullable=True),
        sa.UniqueConstraint('code', name='u_indexes_code')
    )

    op.create_table(
        'index_prices',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('index_code', sa.String(length=64), nullable=False, index=False),
        sa.Column('source', sa.String(length=64), nullable=True),
        sa.Column('price', sa.Float(), nullable=False),
        sa.Column('change', sa.Float(), nullable=True),
        sa.Column('change_percent', sa.Float(), nullable=True),
        sa.Column('timestamp', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
    )
    op.create_index('ix_index_time', 'index_prices', ['index_code', 'timestamp'])
    op.create_unique_constraint('u_index_time', 'index_prices', ['index_code', 'timestamp'])

    op.create_table(
        'index_metadata',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('code', sa.String(length=64), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=True),
        sa.Column('description', sa.String(length=1024), nullable=True),
        sa.Column('source', sa.String(length=64), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.UniqueConstraint('code', name='u_index_metadata_code')
    )

    op.create_table(
        'index_constituents',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('index_code', sa.String(length=64), nullable=False, index=False),
        sa.Column('symbol', sa.String(length=64), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=True),
        sa.Column('weight', sa.Float(), nullable=True),
        sa.Column('shares', sa.Float(), nullable=True),
        sa.Column('market_cap', sa.Float(), nullable=True),
        sa.Column('price', sa.Float(), nullable=True),
        sa.Column('change', sa.Float(), nullable=True),
        sa.Column('change_percent', sa.Float(), nullable=True),
    )
    op.create_index('ix_constituent_index_symbol', 'index_constituents', ['index_code', 'symbol'])

    op.create_table(
        'index_analysis',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('index_code', sa.String(length=64), nullable=False, index=False),
        sa.Column('title', sa.String(length=1024), nullable=True),
        sa.Column('summary', sa.String(length=2048), nullable=True),
        sa.Column('source', sa.String(length=255), nullable=True),
        sa.Column('url', sa.String(length=1024), nullable=True),
        sa.Column('published_at', sa.DateTime(timezone=True), nullable=True),
    )
    op.create_unique_constraint('u_index_analysis_url', 'index_analysis', ['url'])
    op.create_index('ix_index_analysis_index', 'index_analysis', ['index_code'])

    op.create_table(
        'index_news',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('index_code', sa.String(length=64), nullable=False, index=False),
        sa.Column('headline', sa.String(length=1024), nullable=True),
        sa.Column('summary', sa.String(length=2048), nullable=True),
        sa.Column('publisher', sa.String(length=255), nullable=True),
        sa.Column('url', sa.String(length=1024), nullable=True),
        sa.Column('published_at', sa.DateTime(timezone=True), nullable=True),
    )
    op.create_unique_constraint('u_index_news_url', 'index_news', ['url'])
    op.create_index('ix_index_news_index', 'index_news', ['index_code'])


def downgrade():
    op.drop_index('ix_index_news_index', table_name='index_news')
    op.drop_constraint('u_index_news_url', 'index_news', type_='unique')
    op.drop_table('index_news')

    op.drop_index('ix_index_analysis_index', table_name='index_analysis')
    op.drop_constraint('u_index_analysis_url', 'index_analysis', type_='unique')
    op.drop_table('index_analysis')

    op.drop_index('ix_constituent_index_symbol', table_name='index_constituents')
    op.drop_table('index_constituents')

    op.drop_constraint('u_index_metadata_code', 'index_metadata', type_='unique')
    op.drop_table('index_metadata')

    op.drop_constraint('u_index_time', 'index_prices', type_='unique')
    op.drop_index('ix_index_time', table_name='index_prices')
    op.drop_table('index_prices')

    op.drop_table('indexes')
