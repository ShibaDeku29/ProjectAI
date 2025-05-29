from flask import request
from flask_socketio import emit
from sqlalchemy import desc

# Hàm register_events giờ sẽ nhận thêm đối tượng db và current_user
def register_events(socketio, db, current_user):
    from app import Message, User # Import Message và User model

    @socketio.on('message')
    def handle_message(data):
        # Lấy tên người dùng từ Flask-Login nếu người dùng đã đăng nhập
        if current_user.is_authenticated:
            username = current_user.username
        else:
            # Fallback nếu somehow không có người dùng đăng nhập (ví dụ: test trực tiếp socket)
            username = data.get('username', 'Ẩn danh') # Sử dụng tên từ client nếu không đăng nhập

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
        # # Đã bình luận dòng emit tin nhắn hệ thống khi ngắt kết nối
        # if current_user.is_authenticated:
        #     emit('message', {'username': 'Hệ thống', 'message': f'Người dùng {current_user.username} đã rời khỏi.'}, broadcast=True)
        # else:
        #     emit('message', {'username': 'Hệ thống', 'message': f'Một người dùng ({request.sid}) đã rời khỏi.'}, broadcast=True)