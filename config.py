import os

class Config:
    """
    Class chứa các cấu hình cho ứng dụng Flask và SocketIO.
    """
    SECRET_KEY = os.environ.get('SECRET_KEY', 'super-secret-key-default')
    DEBUG = os.environ.get('FLASK_DEBUG', 'True').lower() in ('true', '1', 't')

    # Cấu hình chuỗi kết nối cơ sở dữ liệu PostgreSQL
    # Lấy từ biến môi trường 'DATABASE_URL' khi deploy trên Render
    # Dùng SQLite để phát triển cục bộ nếu biến môi trường không tồn tại
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL', 'sqlite:///site.db')
    SQLALCHEMY_TRACK_MODIFICATIONS = False # Tắt tính năng theo dõi thay đổi của SQLAlchemy để tránh cảnh báo