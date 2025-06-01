# wsgi.py
import eventlet
eventlet.monkey_patch() # Quan trọng: Gọi monkey_patch() ở đây, ngay từ đầu.

# Sau đó mới import ứng dụng Flask của bạn.
# Đảm bảo rằng trong app.py, bạn KHÔNG gọi eventlet.monkey_patch() ở phạm vi toàn cục nữa.
# Khối `if __name__ == '__main__':` trong app.py vẫn có thể giữ lại monkey_patch()
# cho mục đích chạy phát triển bằng `python app.py`.
from app import app as application

# Flask-SocketIO thường tự bọc đối tượng 'app' của Flask.
# Nếu bạn đã khởi tạo `socketio = SocketIO(app)` trong `app.py`,
# thì `application` (chính là Flask app của bạn) là đủ để Gunicorn làm việc.
