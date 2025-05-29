import eventlet
eventlet.monkey_patch()

# events.py (Cập nhật để hỗ trợ Nhắn tin riêng tư)
from flask import request
from flask_socketio import emit
from sqlalchemy import desc

# Biến toàn cục để lưu trữ người dùng đang hoạt động
# Key: username, Value: session_id của SocketIO
active_users_sid_map = {} # Sử dụng tên khác để tránh nhầm lẫn với active_users_list

# Hàm helper để phát danh sách người dùng trực tuyến (cho cả public và private message)
def emit_active_users_list():
    # Lấy danh sách các username duy nhất từ active_users_sid_map
    user_list = sorted(list(active_users_sid_map.keys()))
    emit('update_user_list', user_list, broadcast=True)

# Hàm register_events giờ sẽ nhận thêm đối tượng db và current_user
def register_events(socketio, db, current_user):
    from app import Message, User # Import Message và User model

    @socketio.on('message')
    def handle_message(data):
        # Lấy tên người dùng từ Flask-Login
        if current_user.is_authenticated:
            sender_username = current_user.username
        else:
            sender_username = data.get('username', 'Ẩn danh')

        message_content = data.get('message', '')
        recipient_username = data.get('recipient', 'all') # 'all' cho tin nhắn công khai, hoặc username cụ thể

        if message_content.strip():
            print(f'Tin nhắn từ {sender_username} đến {recipient_username}: {message_content}')

            # 1. Lưu tin nhắn vào cơ sở dữ liệu
            # Đối với tin nhắn riêng tư, chúng ta có thể thêm trường recipient_username vào Message model
            # Hoặc chỉ lưu public messages. Để đơn giản ban đầu, chúng ta sẽ lưu public messages.
            # Nếu muốn lưu private, bạn cần thêm trường recipient_username vào Message model.
            
            # Nếu là tin nhắn công khai, lưu vào DB và broadcast
            if recipient_username == 'all':
                new_message = Message(username=sender_username, message=message_content)
                db.session.add(new_message)
                db.session.commit()
                emit('message', new_message.to_dict(), broadcast=True) # Public message

            # Nếu là tin nhắn riêng tư
            else:
                recipient_sid = active_users_sid_map.get(recipient_username)
                if recipient_sid:
                    # Gửi tin nhắn đến người nhận
                    private_message_data = {
                        'username': sender_username,
                        'message': "(Riêng tư) " + message_content, # Thêm tiền tố để dễ nhận biết
                        'timestamp': datetime.now().isoformat(),
                        'private': True,
                        'recipient': recipient_username
                    }
                    emit('message', private_message_data, room=recipient_sid)
                    
                    # Gửi tin nhắn về cho chính người gửi để họ thấy tin nhắn đã gửi đi
                    emit('message', private_message_data, room=request.sid)
                else:
                    # Người nhận không online hoặc không tồn tại
                    emit('message', {
                        'username': 'Hệ thống',
                        'message': f'Người dùng "{recipient_username}" hiện không trực tuyến hoặc không tồn tại.',
                        'timestamp': datetime.now().isoformat()
                    }, room=request.sid) # Gửi thông báo lỗi chỉ cho người gửi


    @socketio.on('connect')
    def handle_connect():
        print('Client đã kết nối:', request.sid)

        if current_user.is_authenticated:
            # Lưu session_id của người dùng đã đăng nhập
            active_users_sid_map[current_user.username] = request.sid
            emit_active_users_list() # Phát danh sách người dùng mới

        # Gửi lịch sử tin nhắn công khai cho client mới kết nối
        messages = Message.query.order_by(desc(Message.timestamp)).limit(50).all()
        for msg in reversed(messages):
            emit('message', msg.to_dict())


    @socketio.on('disconnect')
    def handle_disconnect():
        print('Client đã ngắt kết nối:', request.sid)
        
        # Xóa người dùng khỏi danh sách active_users_sid_map
        # Cần tìm username từ sid
        disconnected_username = None
        for username, sid in list(active_users_sid_map.items()): # Duyệt qua bản sao để tránh lỗi thay đổi trong khi lặp
            if sid == request.sid:
                disconnected_username = username
                del active_users_sid_map[username]
                break
        
        if disconnected_username:
            emit_active_users_list() # Phát danh sách người dùng mới