import os

class Config:
    """
    Class chứa các cấu hình cho ứng dụng Flask và SocketIO.
    """
    # SECRET_KEY được sử dụng để bảo mật session, CSRF token, v.v.
    # Nên lấy từ biến môi trường khi triển khai thực tế.
    SECRET_KEY = os.environ.get('SECRET_KEY', 'super-secret-key-default')

    # Chế độ debug. 'True' cho phép tải lại nóng và hiển thị lỗi chi tiết.
    # Nên đặt là False trong môi trường production.
    DEBUG = os.environ.get('FLASK_DEBUG', 'True').lower() in ('true', '1', 't')

    # Các cấu hình khác có thể thêm vào đây
    # Ví dụ: Cấu hình cơ sở dữ liệu, API keys, v.v.