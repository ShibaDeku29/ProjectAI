from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '06bb669fb78e'
down_revision = '4e4e9a30daef'
branch_labels = None
depends_on = None

def upgrade():
    # Create friendship table
    op.create_table('friendship',
        sa.Column('user_a_id', sa.Integer(), nullable=False),
        sa.Column('user_b_id', sa.Integer(), nullable=False),
        sa.Column('status', sa.String(length=30), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('accepted_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['user_a_id'], ['user.id'], name='fk_friendship_user_a_id_user'),
        sa.ForeignKeyConstraint(['user_b_id'], ['user.id'], name='fk_friendship_user_b_id_user'),
        sa.PrimaryKeyConstraint('user_a_id', 'user_b_id')
    )

    # Create notification table
    op.create_table('notification',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=128), nullable=False),
        sa.Column('payload_json', sa.Text(), nullable=True),
        sa.Column('is_read', sa.Boolean(), nullable=True),
        sa.Column('timestamp', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['user.id'], name='fk_notification_user_id_user'),
        sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('notification', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_notification_is_read'), ['is_read'], unique=False)
        batch_op.create_index(batch_op.f('ix_notification_timestamp'), ['timestamp'], unique=False)
        batch_op.create_index(batch_op.f('ix_notification_user_id'), ['user_id'], unique=False)

    # Create user_activity table
    op.create_table('user_activity',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('activity_type', sa.String(length=50), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('target_user_id', sa.Integer(), nullable=True),
        sa.Column('target_message_id', sa.Integer(), nullable=True),
        sa.Column('timestamp', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['target_message_id'], ['message.id'], name='fk_useractivity_target_message_id_message'),
        sa.ForeignKeyConstraint(['target_user_id'], ['user.id'], name='fk_useractivity_target_user_id_user'),
        sa.ForeignKeyConstraint(['user_id'], ['user.id'], name='fk_useractivity_user_id_user'),
        sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('user_activity', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_user_activity_timestamp'), ['timestamp'], unique=False)
        batch_op.create_index(batch_op.f('ix_user_activity_user_id'), ['user_id'], unique=False)

    # Modify message table
    with op.batch_alter_table('message', schema=None) as batch_op:
        # Add message_content column as nullable
        batch_op.add_column(sa.Column('message_content', sa.Text(), nullable=True))
        # Add other columns
        batch_op.add_column(sa.Column('is_private', sa.Boolean(), nullable=True))
        batch_op.add_column(sa.Column('recipient_username', sa.String(length=80), nullable=True))
        batch_op.create_index(batch_op.f('ix_message_timestamp'), ['timestamp'], unique=False)

    # Migrate data from message to message_content
    op.execute("UPDATE message SET message_content = message WHERE message IS NOT NULL")
    # Set default value for any NULL message_content
    op.execute("UPDATE message SET message_content = 'Default message' WHERE message_content IS NULL")

    # Apply NOT NULL constraint to message_content
    with op.batch_alter_table('message', schema=None) as batch_op:
        batch_op.alter_column('message_content', nullable=False)
        # Drop the old message column
        batch_op.drop_column('message')

    # Modify user table
    with op.batch_alter_table('user', schema=None) as batch_op:
        batch_op.add_column(sa.Column('created_at', sa.DateTime(), nullable=True))
        batch_op.add_column(sa.Column('avatar_url', sa.String(length=256), nullable=True))
        batch_op.add_column(sa.Column('email', sa.String(length=120), nullable=True))
        batch_op.add_column(sa.Column('full_name', sa.String(length=120), nullable=True))
        batch_op.add_column(sa.Column('bio', sa.Text(), nullable=True))
        batch_op.add_column(sa.Column('last_seen', sa.DateTime(), nullable=True))
        batch_op.create_index(batch_op.f('ix_user_email'), ['email'], unique=True)
        batch_op.create_index(batch_op.f('ix_user_username'), ['username'], unique=True)

def downgrade():
    # Revert user table changes
    with op.batch_alter_table('user', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_user_username'))
        batch_op.drop_index(batch_op.f('ix_user_email'))
        batch_op.drop_column('last_seen')
        batch_op.drop_column('bio')
        batch_op.drop_column('full_name')
        batch_op.drop_column('email')
        batch_op.drop_column('avatar_url')
        batch_op.drop_column('created_at')

    # Revert message table changes
    with op.batch_alter_table('message', schema=None) as batch_op:
        # Add back the old message column
        batch_op.add_column(sa.Column('message', sa.String(length=500), nullable=True))
        # Migrate data back from message_content to message
        op.execute("UPDATE message SET message = message_content WHERE message_content IS NOT NULL")
        batch_op.alter_column('message', nullable=False)
        # Drop new columns and index
        batch_op.drop_index(batch_op.f('ix_message_timestamp'))
        batch_op.drop_column('recipient_username')
        batch_op.drop_column('is_private')
        batch_op.drop_column('message_content')

    # Drop user_activity table
    with op.batch_alter_table('user_activity', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_user_activity_user_id'))
        batch_op.drop_index(batch_op.f('ix_user_activity_timestamp'))
    op.drop_table('user_activity')

    # Drop notification table
    with op.batch_alter_table('notification', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_notification_user_id'))
        batch_op.drop_index(batch_op.f('ix_notification_timestamp'))
        batch_op.drop_index(batch_op.f('ix_notification_is_read'))
    op.drop_table('notification')

    # Drop friendship table
    op.drop_table('friendship')     