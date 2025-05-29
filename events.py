from flask import request
from flask_socketio import emit

def register_events(socketio):
    """
    Hàm này đăng ký tất cả các xử lý sự kiện SocketIO.
    Truyền đối tượng socketio từ app.py vào để đăng ký các sự kiện.
    """

    @socketio.on('message')
    def handle_message(data):
        """
        Xử lý sự kiện 'message' khi client gửi tin nhắn.
        Dữ liệu mong đợi là một từ điển với 'username' và 'message'.
        """
        username = data.get('username', 'Ẩn danh') # Lấy tên người dùng, mặc định 'Ẩn danh'
        message = data.get('message', '') # Lấy nội dung tin nhắn

        # Chỉ xử lý tin nhắn nếu không rỗng sau khi loại bỏ khoảng trắng
        if message.strip():
            print(f'Tin nhắn từ {username}: {message}')
            # Phát lại tin nhắn tới tất cả các client đã kết nối
            emit('message', {'username': username, 'message': message}, broadcast=True)

    @socketio.on('connect')
    def handle_connect():
        """
        Xử lý sự kiện 'connect' khi một client mới kết nối.
        Sử dụng request.sid để lấy ID phiên của client.
        """
        print('Client đã kết nối:', request.sid)
        # Gửi thông báo hệ thống tới tất cả các client về người dùng mới tham gia
        emit('message', {'username': 'Hệ thống', 'message': f'Một người dùng mới ({request.sid}) đã tham gia.'}, broadcast=True)

    @socketio.on('disconnect')
    def handle_disconnect():
        """
        Xử lý sự kiện 'disconnect' khi một client ngắt kết nối.
        Sử dụng request.sid để lấy ID phiên của client.
        """
        print('Client đã ngắt kết nối:', request.sid)
        # Gửi thông báo hệ thống tới tất cả các client về việc người dùng rời đi
        emit('message', {'username': 'Hệ thống', 'message': f'Một người dùng ({request.sid}) đã rời khỏi.'}, broadcast=True)

    # Bạn có thể thêm các xử lý sự kiện SocketIO khác ở đây.
    # Ví dụ về một sự kiện 'typing' (đang gõ):
    # @socketio.on('typing')
    # def handle_typing(data):
    #     # Phát sự kiện 'typing_indicator' tới các client khác (không bao gồm người gửi)
    #     emit('typing_indicator', {'username': data.get('username', 'Ẩn danh')}, broadcast=True, include_self=False)