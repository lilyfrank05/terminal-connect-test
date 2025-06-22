"""Add postback_column_preferences to users table for v1.2.0 upgrade

Revision ID: 74acd8d08219
Revises: 
Create Date: 2025-06-22 12:09:29.735256

This migration upgrades from v1.1.1 to v1.2.0 by adding the missing
postback_column_preferences column to existing users table.
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '74acd8d08219'
down_revision = None  # This is the first migration for existing v1.1.1 databases
branch_labels = None
depends_on = None


def upgrade():
    # Check if users table exists, if not create all tables
    # This handles both fresh installs and upgrades from v1.1.1
    
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing_tables = inspector.get_table_names()
    
    if 'users' not in existing_tables:
        # Fresh install - create all tables
        print("Creating all tables for fresh installation...")
        
        # Create invites table
        op.create_table('invites',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('email', sa.String(length=120), nullable=False),
            sa.Column('token', sa.String(length=255), nullable=False),
            sa.Column('created_at', sa.DateTime(), nullable=True),
            sa.Column('expires_at', sa.DateTime(), nullable=True),
            sa.Column('used', sa.Boolean(), nullable=True),
            sa.Column('used_at', sa.DateTime(), nullable=True),
            sa.PrimaryKeyConstraint('id'),
            sa.UniqueConstraint('token')
        )
        op.create_index('ix_invites_email', 'invites', ['email'])

        # Create users table with postback_column_preferences
        op.create_table('users',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('email', sa.String(length=120), nullable=False),
            sa.Column('password_hash', sa.String(length=255), nullable=False),
            sa.Column('role', sa.String(length=20), nullable=False),
            sa.Column('is_active', sa.Boolean(), nullable=True),
            sa.Column('created_at', sa.DateTime(), nullable=True),
            sa.Column('updated_at', sa.DateTime(), nullable=True),
            sa.Column('last_login', sa.DateTime(), nullable=True),
            sa.Column('reset_token', sa.String(length=255), nullable=True),
            sa.Column('reset_token_expires', sa.DateTime(), nullable=True),
            sa.Column('postback_column_preferences', sa.Text(), nullable=True),
            sa.PrimaryKeyConstraint('id'),
            sa.UniqueConstraint('email')
        )

        # Create user_configs table
        op.create_table('user_configs',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('user_id', sa.Integer(), nullable=False),
            sa.Column('name', sa.String(length=100), nullable=False),
            sa.Column('config_data', sa.Text(), nullable=False),
            sa.Column('created_at', sa.DateTime(), nullable=True),
            sa.Column('updated_at', sa.DateTime(), nullable=True),
            sa.Column('display_order', sa.Integer(), nullable=False),
            sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
            sa.PrimaryKeyConstraint('id')
        )

        # Create user_postbacks table
        op.create_table('user_postbacks',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('user_id', sa.Integer(), nullable=False),
            sa.Column('transaction_id', sa.String(length=255), nullable=False),
            sa.Column('intent_id', sa.String(length=255), nullable=True),
            sa.Column('postback_data', sa.Text(), nullable=False),
            sa.Column('created_at', sa.DateTime(), nullable=True),
            sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
            sa.PrimaryKeyConstraint('id')
        )
        op.create_index('ix_user_postbacks_intent_id', 'user_postbacks', ['intent_id'])
        op.create_index('ix_user_postbacks_transaction_id', 'user_postbacks', ['transaction_id'])
        
    else:
        # Upgrade from v1.1.1 - add missing columns
        print("Upgrading existing database from v1.1.1...")
        
        # Check if postback_column_preferences already exists
        columns = [col['name'] for col in inspector.get_columns('users')]
        if 'postback_column_preferences' not in columns:
            print("Adding postback_column_preferences column to users table...")
            op.add_column('users', sa.Column('postback_column_preferences', sa.Text(), nullable=True))
        
        # Check if display_order exists in user_configs
        if 'user_configs' in existing_tables:
            config_columns = [col['name'] for col in inspector.get_columns('user_configs')]
            if 'display_order' not in config_columns:
                print("Adding display_order column to user_configs table...")
                op.add_column('user_configs', sa.Column('display_order', sa.Integer(), nullable=False, server_default='0'))


def downgrade():
    # Remove added columns
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing_tables = inspector.get_table_names()
    
    if 'users' in existing_tables:
        columns = [col['name'] for col in inspector.get_columns('users')]
        if 'postback_column_preferences' in columns:
            op.drop_column('users', 'postback_column_preferences')
    
    if 'user_configs' in existing_tables:
        config_columns = [col['name'] for col in inspector.get_columns('user_configs')]
        if 'display_order' in config_columns:
            op.drop_column('user_configs', 'display_order')
