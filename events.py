from flask import request, current_app
from flask_socketio import emit
from sqlalchemy import desc # Để sắp xếp tin nhắn theo thời gian mới nhất

# Hàm register_events giờ sẽ nhận thêm đối tượng db
def register_events(socketio, db):
    # Import Message model bên trong hàm để tránh lỗi import vòng tròn
    # Vì Message model được định nghĩa trong app.py
    from app import Message

    @socketio.on('message')
    def handle_message(data):
        username = data.get('username', 'Ẩn danh')
        message_content = data.get('message', '') # Đổi tên biến để tránh trùng lặp

        if message_content.strip():
            print(f'Tin nhắn từ {username}: {message_content}')

            # 1. Lưu tin nhắn vào cơ sở dữ liệu
            new_message = Message(username=username, message=message_content)
            db.session.add(new_message)
            db.session.commit() # Commit tin nhắn vào DB

            # 2. Phát tin nhắn đã lưu (đã bao gồm timestamp từ DB) tới tất cả các client
            emit('message', new_message.to_dict(), broadcast=True)

    @socketio.on('connect')
    def handle_connect():
        print('Client đã kết nối:', request.sid)

        # 1. Tải và gửi lịch sử tin nhắn cho client mới kết nối
        # Lấy 50 tin nhắn gần nhất, sắp xếp theo thời gian mới nhất (desc)
        # Sau đó đảo ngược danh sách để tin nhắn cũ nhất lên trên
        messages = Message.query.order_by(desc(Message.timestamp)).limit(50).all()
        for msg in reversed(messages):
            emit('message', msg.to_dict()) # Gửi từng tin nhắn cho client hiện tại (không broadcast)

        # 2. Gửi thông báo hệ thống về việc có người dùng mới tham gia
        emit('message', {'username': 'Hệ thống', 'message': f'Một người dùng mới ({request.sid}) đã tham gia.'}, broadcast=True)


    @socketio.on('disconnect')
    def handle_disconnect():
        print('Client đã ngắt kết nối:', request.sid)
        emit('message', {'username': 'Hệ thống', 'message': f'Một người dùng ({request.sid}) đã rời khỏi.'}, broadcast=True)