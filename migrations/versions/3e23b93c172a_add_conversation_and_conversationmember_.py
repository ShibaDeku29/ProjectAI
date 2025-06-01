"""Add Conversation and ConversationMember models

Revision ID: 3e23b93c172a
Revises: 06bb669fb78e
Create Date: 2025-06-02 00:00:00.000000
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '3e23b93c172a'
down_revision = '06bb669fb78e'
branch_labels = None
depends_on = None

def upgrade():
    # Create conversation table
    op.create_table('conversation',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=100), nullable=True),
        sa.Column('is_group', sa.Boolean(), nullable=False, server_default='0'),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )

    # Create conversation_member table
    op.create_table('conversation_member',
        sa.Column('conversation_id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('joined_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['conversation_id'], ['conversation.id'], name='fk_conversation_member_conversation_id'),
        sa.ForeignKeyConstraint(['user_id'], ['user.id'], name='fk_conversation_member_user_id'),
        sa.PrimaryKeyConstraint('conversation_id', 'user_id')
    )

    # Create a default conversation for existing messages
    op.execute("INSERT INTO conversation (name, is_group, created_at) VALUES ('Legacy Public Chat', TRUE, CURRENT_TIMESTAMP)")

    # Add columns to message table (nullable initially)
    with op.batch_alter_table('message', schema=None) as batch_op:
        batch_op.drop_index('ix_message_timestamp')
        batch_op.add_column(sa.Column('conversation_id', sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column('sender_id', sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column('is_read', sa.Boolean(), nullable=True, server_default='0'))

    # Backfill conversation_id and sender_id for existing messages
    op.execute("""
        UPDATE message
        SET conversation_id = (SELECT id FROM conversation WHERE name = 'Legacy Public Chat' LIMIT 1),
            sender_id = (SELECT id FROM "user" WHERE username = message.username LIMIT 1)
        WHERE is_private = FALSE
    """)
    op.execute("""
        UPDATE message
        SET conversation_id = (SELECT id FROM conversation WHERE name = 'Legacy Public Chat' LIMIT 1),
            sender_id = (SELECT id FROM "user" WHERE username = message.username LIMIT 1)
        WHERE is_private = TRUE
    """)

    # Enforce NOT NULL constraints and add foreign keys
    with op.batch_alter_table('message', schema=None) as batch_op:
        batch_op.alter_column('conversation_id', nullable=False)
        batch_op.alter_column('sender_id', nullable=False)
        batch_op.create_foreign_key('fk_message_conversation_id', 'conversation', ['conversation_id'], ['id'])
        batch_op.create_foreign_key('fk_message_sender_id', 'user', ['sender_id'], ['id'])
        batch_op.create_index(batch_op.f('ix_message_timestamp'), ['timestamp'], unique=False)
        batch_op.drop_column('is_private')
        batch_op.drop_column('recipient_username')
        batch_op.drop_column('username')

def downgrade():
    with op.batch_alter_table('message', schema=None) as batch_op:
        batch_op.drop_constraint('fk_message_sender_id', type_='foreignkey')
        batch_op.drop_constraint('fk_message_conversation_id', type_='foreignkey')
        batch_op.drop_index('ix_message_timestamp')
        batch_op.add_column(sa.Column('username', sa.String(length=80), nullable=False))
        batch_op.add_column(sa.Column('recipient_username', sa.String(length=80), nullable=True))
        batch_op.add_column(sa.Column('is_private', sa.Boolean(), nullable=True))
        batch_op.drop_column('is_read')
        batch_op.drop_column('sender_id')
        batch_op.drop_column('conversation_id')
        batch_op.create_index('ix_message_timestamp', ['timestamp'], unique=False)

    op.drop_table('conversation_member')
    op.drop_table('conversation')