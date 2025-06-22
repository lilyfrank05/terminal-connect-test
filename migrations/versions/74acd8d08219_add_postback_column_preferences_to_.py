"""Add postback_column_preferences to users table for PostgreSQL

Revision ID: 74acd8d08219
Revises: 1646a6a066a5
Create Date: 2025-06-22 12:09:29.735256

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '74acd8d08219'
down_revision = '1646a6a066a5'
branch_labels = None
depends_on = None


def upgrade():
    # Add postback_column_preferences column to users table
    # This handles the case where PostgreSQL database exists but lacks this column
    op.add_column('users', sa.Column('postback_column_preferences', sa.Text(), nullable=True))


def downgrade():
    # Remove postback_column_preferences column from users table
    op.drop_column('users', 'postback_column_preferences')
