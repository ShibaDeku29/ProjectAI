from flask import request
from flask_socketio import emit
from sqlalchemy import desc
from datetime import datetime

# Global dictionary to store active users: {username: session_id}
active_users_sid_map = {}

# Helper function to broadcast the list of online users
def emit_active_users_list():
    user_list = sorted(list(active_users_sid_map.keys()))
    emit('update_user_list', user_list, broadcast=True)

# Register Socket.IO event handlers
def register_events(socketio, db, current_user):
    from app import Message, User  # Import models here to avoid circular imports

    @socketio.on('message')
    def handle_message(data):
        if not current_user.is_authenticated:
            emit('error', {'message': 'Vui lòng đăng nhập để gửi tin nhắn.'}, room=request.sid)
            return

        sender_username = current_user.username
        message_content = data.get('message', '').strip()
        recipient_username = data.get('recipient', 'all')

        # Validate message content
        if not message_content:
            emit('error', {'message': 'Tin nhắn không được để trống!'}, room=request.sid)
            return
        if len(message_content) > 500:
            emit('error', {'message': 'Tin nhắn không được vượt quá 500 ký tự!'}, room=request.sid)
            return

        print(f'Tin nhắn từ {sender_username} đến {recipient_username}: {message_content}')

        if recipient_username == 'all':
            # Public message
            new_message = Message(
                username=sender_username,
                message_content=message_content,
                is_private=False,
                timestamp=datetime.utcnow()
            )
            db.session.add(new_message)
            db.session.commit()
            emit('message', new_message.to_dict(), broadcast=True)
        else:
            # Private message
            recipient_user = User.query.filter_by(username=recipient_username).first()
            if not recipient_user:
                emit('message', {
                    'username': 'Hệ thống',
                    'message': f'Người dùng "{recipient_username}" không tồn tại.',
                    'timestamp': datetime.utcnow().isoformat(),
                    'private': True,
                    'recipient': sender_username
                }, room=request.sid)
                return

            recipient_sid = active_users_sid_map.get(recipient_username)
            if recipient_sid:
                private_message = Message(
                    username=sender_username,
                    message_content=message_content,
                    is_private=True,
                    recipient_username=recipient_username,
                    timestamp=datetime.utcnow()
                )
                db.session.add(private_message)
                db.session.commit()
                
                private_message_data = private_message.to_dict()
                private_message_data['message'] = "(Riêng tư) " + message_content
                
                # Send to recipient
                emit('message', private_message_data, room=recipient_sid)
                # Send back to sender
                emit('message', private_message_data, room=request.sid)
            else:
                emit('message', {
                    'username': 'Hệ thống',
                    'message': f'Người dùng "{recipient_username}" hiện không trực tuyến.',
                    'timestamp': datetime.utcnow().isoformat(),
                    'private': True,
                    'recipient': sender_username
                }, room=request.sid)

    @socketio.on('connect')
    def handle_connect():
        if not current_user.is_authenticated:
            emit('error', {'message': 'Vui lòng đăng nhập để tham gia chat.'}, room=request.sid)
            socketio.close_room(request.sid)
            return

        print(f'Client đã kết nối: {request.sid} (Người dùng: {current_user.username})')
        active_users_sid_map[current_user.username] = request.sid
        emit_active_users_list()

        # Send public message history (last 50 public messages)
        messages = Message.query.filter_by(is_private=False).order_by(Message.timestamp.asc()).limit(50).all()
        history_to_send = [msg.to_dict() for msg in messages]
        if history_to_send:
            emit('message_history', history_to_send, room=request.sid)

        # Send welcome message to the connected user
        emit('message', {
            'username': 'Hệ thống',
            'message': f'Chào mừng {current_user.username} đến với phòng chat!',
            'timestamp': datetime.utcnow().isoformat(),
            'private': False
        }, room=request.sid)

    @socketio.on('disconnect')
    def handle_disconnect():
        print(f'Client đã ngắt kết nối: {request.sid}')
        disconnected_username = None
        for username, sid in list(active_users_sid_map.items()):
            if sid == request.sid:
                disconnected_username = username
                del active_users_sid_map[username]
                break
        
        if disconnected_username:
            print(f'Người dùng {disconnected_username} đã ngắt kết nối.')
            emit_active_users_list()