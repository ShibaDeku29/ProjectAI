from flask import request
from flask_socketio import SocketIO, emit, join_room
from sqlalchemy import or_
from sqlalchemy.exc import SQLAlchemyError, IntegrityError
from datetime import datetime
import logging

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Global dictionary to store active user sessions: {username: session_id}
user_sessions = {}

def emit_online_friends(socketio: SocketIO, db, user_id: int):
    """Broadcast the list of online friends to the user."""
    try:
        # Optimized query using join to fetch friends
        friends = db.session.query(User.username).join(
            Friendship, or_(
                Friendship.user_a_id == User.id,
                Friendship.user_b_id == User.id
            )
        ).filter(
            or_(
                Friendship.user_a_id == user_id,
                Friendship.user_b_id == user_id
            ),
            Friendship.status == 'friends'
        ).all()
        online_friends = [f.username for f in friends if f.username in user_sessions]
        username = db.session.query(User).filter_by(id=user_id).first().username
        emit('update_user_list', sorted(online_friends), room=user_sessions.get(username))
        logger.info(f"Emitted online friends list to user {username}: {online_friends}")
    except SQLAlchemyError as e:
        logger.error(f"Error fetching online friends for user_id {user_id}: {str(e)}")

def register_events(socketio: SocketIO, db, current_user):
    from app import Message, User, Conversation, ConversationMember, Friendship, Notification

    @socketio.on('connect')
    def handle_connect():
        if not current_user.is_authenticated:
            emit('error', {'message': 'Vui lòng đăng nhập để tham gia chat.'}, room=request.sid)
            socketio.close_room(request.sid)
            logger.warning(f"Unauthorized connection attempt: {request.sid}")
            return

        username = current_user.username
        logger.info(f'Client connected: {request.sid} (User: {username})')
        user_sessions[username] = request.sid

        # Join active conversation rooms (limit to recent 50 for performance)
        try:
            conversations = db.session.query(Conversation).join(ConversationMember).filter(
                ConversationMember.user_id == current_user.id
            ).order_by(Conversation.created_at.desc()).limit(50).all()
            for convo in conversations:
                join_room(f'conversation_{convo.id}')
                logger.debug(f'User {username} joined room conversation_{convo.id}')
        except SQLAlchemyError as e:
            logger.error(f"Error joining conversation rooms for user {username}: {str(e)}")

        emit_online_friends(socketio, db, current_user.id)

        emit('welcome', {
            'username': 'Hệ thống',
            'content': f'Chào mừng {username} đến với ProjectAI Chat!',
            'timestamp': datetime.utcnow().isoformat()
        }, room=request.sid)

    @socketio.on('disconnect')
    def handle_disconnect():
        logger.info(f'Client disconnected: {request.sid}')
        disconnected_username = None
        for username, sid in list(user_sessions.items()):
            if sid == request.sid:
                disconnected_username = username
                del user_sessions[username]
                break
        
        if disconnected_username:
            logger.info(f'User {disconnected_username} disconnected.')
            try:
                user = db.session.query(User).filter_by(username=disconnected_username).first()
                if user:
                    emit_online_friends(socketio, db, user.id)
            except SQLAlchemyError as e:
                logger.error(f"Error updating friends list on disconnect for {disconnected_username}: {str(e)}")

    @socketio.on('message')
    def handle_message(data):
        if not current_user.is_authenticated:
            emit('error', {'message': 'Vui lòng đăng nhập để gửi tin nhắn.'}, room=request.sid)
            return

        conversation_id = data.get('conversation_id')
        content = data.get('content', '').strip()

        if not conversation_id or not content:
            emit('error', {'message': 'Cuộc trò chuyện và nội dung tin nhắn là bắt buộc!'}, room=request.sid)
            logger.warning(f"Invalid message data from {current_user.username}: {data}")
            return
        if len(content) > 500:
            emit('error', {'message': 'Tin nhắn không được vượt quá 500 ký tự!'}, room=request.sid)
            return

        try:
            conversation = db.session.query(Conversation).get(conversation_id)
            if not conversation or not db.session.query(ConversationMember).filter_by(
                conversation_id=conversation_id, user_id=current_user.id).first():
                emit('error', {'message': 'Bạn không có quyền gửi tin nhắn trong cuộc trò chuyện này!'}, room=request.sid)
                logger.warning(f"Unauthorized message attempt by {current_user.username} in conversation {conversation_id}")
                return

            message = Message(
                conversation_id=conversation_id,
                sender_id=current_user.id,
                content=content,
                timestamp=datetime.utcnow()
            )
            db.session.add(message)
            db.session.flush()  # Get message ID before commit

            # Create notifications for other members
            members = db.session.query(ConversationMember).filter_by(conversation_id=conversation_id).filter(
                ConversationMember.user_id != current_user.id).all()
            for member in members:
                notification = Notification(
                    user_id=member.user_id,
                    name='new_message',
                    payload_json=f'{{"conversation_id": {conversation_id}, "from_username": "{current_user.username}"}}'
                )
                db.session.add(notification)

            db.session.commit()
            message_dict = message.to_dict()
            emit('message', message_dict, room=f'conversation_{conversation_id}')
            logger.info(f"Message sent by {current_user.username} in conversation {conversation_id}: {content}")
        except IntegrityError:
            db.session.rollback()
            emit('error', {'message': 'Lỗi dữ liệu: Tin nhắn không thể được lưu.'}, room=request.sid)
            logger.error(f"IntegrityError sending message by {current_user.username}: {data}")
        except SQLAlchemyError as e:
            db.session.rollback()
            emit('error', {'message': f'Lỗi khi gửi tin nhắn: {str(e)}'}, room=request.sid)
            logger.error(f"SQLAlchemyError sending message by {current_user.username}: {str(e)}")

    @socketio.on('typing')
    def handle_typing(data):
        conversation_id = data.get('conversation_id')
        if not conversation_id:
            return

        try:
            if db.session.query(ConversationMember).filter_by(
                conversation_id=conversation_id, user_id=current_user.id).first():
                emit('typing', {
                    'username': current_user.username,
                    'conversation_id': conversation_id
                }, room=f'conversation_{conversation_id}', include_self=False)
                logger.debug(f"Typing event by {current_user.username} in conversation {conversation_id}")
        except SQLAlchemyError as e:
            logger.error(f"Error handling typing event for {current_user.username}: {str(e)}")

    @socketio.on('read_message')
    def handle_read_message(data):
        message_id = data.get('message_id')
        if not message_id:
            return

        try:
            message = db.session.query(Message).get(message_id)
            if message and db.session.query(ConversationMember).filter_by(
                conversation_id=message.conversation_id, user_id=current_user.id).first() and not message.is_read:
                message.is_read = True
                db.session.commit()
                emit('message_read', {'message_id': message_id}, room=f'conversation_{message.conversation_id}')
                logger.info(f"Message {message_id} marked as read by {current_user.username}")
        except SQLAlchemyError as e:
            db.session.rollback()
            logger.error(f"Error marking message {message_id} as read: {str(e)}")