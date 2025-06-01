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

    # Add columns to message table (nullable initially)
    with op.batch_alter_table('message', schema=None) as batch_op:
        batch_op.drop_index('ix_message_timestamp')
        batch_op.add_column(sa.Column('conversation_id', sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column('sender_id', sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column('is_read', sa.Boolean(), nullable=True, server_default='0'))

    # Delete messages with invalid username
    op.execute("""
        DELETE FROM message
        WHERE username NOT IN (SELECT username FROM "user");
    """)

    # Create a default public conversation for public messages
    op.execute("INSERT INTO conversation (name, is_group, created_at) VALUES ('Legacy Public Chat', TRUE, CURRENT_TIMESTAMP)")

    # Backfill public messages
    op.execute("""
        UPDATE message
        SET conversation_id = (SELECT id FROM conversation WHERE name = 'Legacy Public Chat' LIMIT 1),
            sender_id = (SELECT id FROM "user" WHERE username = message.username LIMIT 1)
        WHERE is_private = FALSE
    """)

    # Create conversations for private message pairs
    op.execute("""
        INSERT INTO conversation (is_group, created_at)
        SELECT FALSE, CURRENT_TIMESTAMP
        FROM (
            SELECT DISTINCT LEAST(username, recipient_username) AS user1,
                            GREATEST(username, recipient_username) AS user2
            FROM message
            WHERE is_private = TRUE AND recipient_username IS NOT NULL
        ) pairs
    """)

    # Add conversation members for private conversations
    op.execute("""
        INSERT INTO conversation_member (conversation_id, user_id, joined_at)
        SELECT c.id, u.id, CURRENT_TIMESTAMP
        FROM conversation c
        CROSS JOIN (
            SELECT DISTINCT username FROM message WHERE is_private = TRUE
            UNION
            SELECT DISTINCT recipient_username FROM message WHERE is_private = TRUE AND recipient_username IS NOT NULL
        ) m
        JOIN "user" u ON u.username = m.username
        WHERE c.is_group = FALSE
        AND EXISTS (
            SELECT 1
            FROM message m2
            WHERE m2.is_private = TRUE
            AND (
                (m2.username = u.username AND m2.recipient_username IN (
                    SELECT username FROM "user" WHERE id IN (
                        SELECT user_id FROM conversation_member WHERE conversation_id = c.id
                    )
                ))
                OR
                (m2.recipient_username = u.username AND m2.username IN (
                    SELECT username FROM "user" WHERE id IN (
                        SELECT user_id FROM conversation_member WHERE conversation_id = c.id
                    )
                ))
            )
        )
    """)

    # Backfill private messages
    op.execute("""
        UPDATE message
        SET conversation_id = (
            SELECT c.id
            FROM conversation c
            JOIN conversation_member cm1 ON cm1.conversation_id = c.id
            JOIN conversation_member cm2 ON cm2.conversation_id = c.id AND cm2.user_id != cm1.user_id
            JOIN "user" u1 ON u1.id = cm1.user_id
            JOIN "user" u2 ON u2.id = cm2.user_id
            WHERE c.is_group = FALSE
            AND (
                (u1.username = message.username AND u2.username = message.recipient_username)
                OR
                (u1.username = message.recipient_username AND u2.username = message.username)
            )
            LIMIT 1
        ),
        sender_id = (SELECT id FROM "user" WHERE username = message.username LIMIT 1)
        WHERE is_private = TRUE
    """)

    # Remove any messages that still have NULL conversation_id or sender_id
    op.execute("DELETE FROM message WHERE conversation_id IS NULL OR sender_id IS NULL")

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