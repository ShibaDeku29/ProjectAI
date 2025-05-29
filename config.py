import os

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY', 'super-secret-key-default')
    DEBUG = os.environ.get('FLASK_DEBUG', 'True').lower() in ('true', '1', 't')

    # Ứng dụng sẽ tìm biến môi trường MONGO_URI.
    # Nếu không tìm thấy (ví dụ: khi chạy cục bộ mà không đặt biến môi trường),
    # nó sẽ mặc định kết nối tới MongoDB chạy trên localhost.
    MONGO_URI = os.environ.get('MONGO_URI', 'mongodb://localhost:27017/chat_db')