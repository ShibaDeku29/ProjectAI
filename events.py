# events.py (Cập nhật để theo dõi người dùng trực tuyến)
from flask import request
from flask_socketio import emit
from sqlalchemy import desc

# Biến toàn cục để lưu trữ người dùng đang hoạt động
# Key: session_id của SocketIO, Value: username của người dùng
active_users = {}

# Hàm helper để phát danh sách người dùng trực tuyến
def emit_active_users_list():
    # Lấy danh sách các username duy nhất từ active_users
    # Convert set to list for JSON serialization
    user_list = sorted(list(set(active_users.values())))
    emit('update_user_list', user_list, broadcast=True)

# Hàm register_events giờ sẽ nhận thêm đối tượng db và current_user
def register_events(socketio, db, current_user):
    from app import Message, User # Import Message và User model

    @socketio.on('message')
    def handle_message(data):
        if current_user.is_authenticated:
            username = current_user.username
        else:
            username = data.get('username', 'Ẩn danh')

        message_content = data.get('message', '')

        if message_content.strip():
            print(f'Tin nhắn từ {username}: {message_content}')

            new_message = Message(username=username, message=message_content)
            db.session.add(new_message)
            db.session.commit()

            emit('message', new_message.to_dict(), broadcast=True)

    @socketio.on('connect')
    def handle_connect():
        print('Client đã kết nối:', request.sid)

        # Thêm người dùng vào danh sách active_users nếu họ đã đăng nhập
        if current_user.is_authenticated:
            active_users[request.sid] = current_user.username
            emit_active_users_list() # Phát danh sách người dùng mới

        # Gửi lịch sử tin nhắn cho client mới kết nối
        messages = Message.query.order_by(desc(Message.timestamp)).limit(50).all()
        for msg in reversed(messages):
            emit('message', msg.to_dict())

        # # Đã bình luận dòng emit tin nhắn hệ thống khi kết nối
        # if current_user.is_authenticated:
        #     emit('message', {'username': 'Hệ thống', 'message': f'Người dùng {current_user.username} đã tham gia.'}, broadcast=True)
        # else:
        #     emit('message', {'username': 'Hệ thống', 'message': f'Một người dùng mới ({request.sid}) đã tham gia.'}, broadcast=True)


    @socketio.on('disconnect')
    def handle_disconnect():
        print('Client đã ngắt kết nối:', request.sid)
        
        # Xóa người dùng khỏi danh sách active_users
        if request.sid in active_users:
            del active_users[request.sid]
            emit_active_users_list() # Phát danh sách người dùng mới

        # # Đã bình luận dòng emit tin nhắn hệ thống khi ngắt kết nối
        # if current_user.is_authenticated:
        #     emit('message', {'username': 'Hệ thống', 'message': f'Người dùng {current_user.username} đã rời khỏi.'}, broadcast=True)
        # else:
        #     emit('message', {'username': 'Hệ thống', 'message': f'Một người dùng ({request.sid}) đã rời khỏi.'}, broadcast=True)