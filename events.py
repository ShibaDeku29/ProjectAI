import eventlet
eventlet.monkey_patch()

from flask import request
from flask_socketio import emit
from sqlalchemy import desc
from datetime import datetime # <<< THÊM DÒNG NÀY ĐỂ IMPORT DATETIME

# Biến toàn cục để lưu trữ người dùng đang hoạt động
# Key: username, Value: session_id của SocketIO
active_users_sid_map = {}

# Hàm helper để phát danh sách người dùng trực tuyến
def emit_active_users_list():
    user_list = sorted(list(active_users_sid_map.keys()))
    emit('update_user_list', user_list, broadcast=True)

# Hàm register_events giờ sẽ nhận thêm đối tượng db và current_user
def register_events(socketio, db, current_user):
    from app import Message, User # Import Message và User model ở đây để tránh circular import

    @socketio.on('message')
    def handle_message(data):
        sender_username = "Ẩn danh" # Mặc định nếu không xác thực được
        if current_user.is_authenticated:
            sender_username = current_user.username
        # Trong trường hợp client gửi username (ví dụ: client cũ hơn hoặc kịch bản không dùng Flask-Login cho SocketIO)
        # thì có thể ưu tiên current_user.username nếu có.
        # Tuy nhiên, với @login_required trên route chat và SocketIO thường chia sẻ context session,
        # current_user.is_authenticated nên là nguồn chính.
        # else:
        #     sender_username = data.get('username', 'Ẩn danh')


        message_content = data.get('message', '')
        recipient_username = data.get('recipient', 'all') # 'all' cho tin nhắn công khai

        if message_content.strip(): # Chỉ xử lý nếu tin nhắn không trống
            print(f'Tin nhắn từ {sender_username} đến {recipient_username}: {message_content}')

            if recipient_username == 'all':
                # Tin nhắn công khai
                new_message = Message(username=sender_username, message=message_content)
                db.session.add(new_message)
                db.session.commit()
                emit('message', new_message.to_dict(), broadcast=True)
            else:
                # Tin nhắn riêng tư
                recipient_sid = active_users_sid_map.get(recipient_username)
                if recipient_sid:
                    private_message_data = {
                        'username': sender_username,
                        'message': "(Riêng tư) " + message_content,
                        'timestamp': datetime.now().isoformat(),
                        'private': True,
                        'recipient': recipient_username
                    }
                    # Gửi đến người nhận
                    emit('message', private_message_data, room=recipient_sid)
                    # Gửi lại cho người gửi để xác nhận
                    emit('message', private_message_data, room=request.sid)
                else:
                    # Thông báo cho người gửi nếu người nhận không online
                    emit('message', {
                        'username': 'Hệ thống',
                        'message': f'Người dùng "{recipient_username}" hiện không trực tuyến hoặc không tồn tại.',
                        'timestamp': datetime.now().isoformat(),
                        'private': True, # Vẫn là tin nhắn riêng cho người gửi
                        'recipient': sender_username # Người nhận của thông báo này là chính người gửi
                    }, room=request.sid)
        else:
            # (Tùy chọn) Gửi thông báo lỗi nếu tin nhắn trống
            emit('error', {'message': 'Tin nhắn không được để trống!'}, room=request.sid)


    @socketio.on('connect')
    def handle_connect():
        print(f'Client đã kết nối: {request.sid}')
        if current_user.is_authenticated:
            print(f'Người dùng đã xác thực: {current_user.username}')
            active_users_sid_map[current_user.username] = request.sid
            emit_active_users_list() # Cập nhật danh sách cho mọi người

            # Gửi lịch sử tin nhắn công khai (chỉ những tin không riêng tư) cho client mới kết nối
            # Giả sử Message model không có trường để phân biệt public/private
            # Nếu có, bạn có thể filter Message.query.filter_by(is_private=False)
            messages = Message.query.order_by(Message.timestamp.asc()).limit(50).all() # Lấy 50 tin cũ nhất, theo thứ tự thời gian
            # Hoặc lấy 50 tin mới nhất: Message.query.order_by(desc(Message.timestamp)).limit(50).all() rồi reversed()
            
            history_to_send = [msg.to_dict() for msg in messages]
            if history_to_send:
                 emit('message_history', history_to_send, room=request.sid) # Gửi lịch sử chỉ cho client này

            # Gửi thông báo chào mừng riêng cho người dùng vừa kết nối
            emit('message', {
                'username': 'Hệ thống',
                'message': f'Chào mừng {current_user.username} đến với phòng chat!',
                'timestamp': datetime.now().isoformat()
            }, room=request.sid)

        else:
            # Xử lý trường hợp người dùng chưa đăng nhập kết nối (nếu có thể xảy ra)
            # Có thể ngắt kết nối hoặc gửi thông báo yêu cầu đăng nhập
            print(f'Client chưa xác thực kết nối: {request.sid}')
            # emit('error', {'message': 'Vui lòng đăng nhập để tham gia chat.'}, room=request.sid)
            # close_room(request.sid) # Cân nhắc nếu muốn tự động ngắt kết nối


    @socketio.on('disconnect')
    def handle_disconnect():
        print(f'Client đã ngắt kết nối: {request.sid}')
        disconnected_username = None
        for username, sid in list(active_users_sid_map.items()): # Duyệt qua bản sao để an toàn khi xóa
            if sid == request.sid:
                disconnected_username = username
                del active_users_sid_map[username]
                break
        
        if disconnected_username:
            print(f'Người dùng {disconnected_username} đã ngắt kết nối.')
            emit_active_users_list() # Cập nhật danh sách cho mọi người