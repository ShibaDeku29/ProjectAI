import os
from flask import Flask, render_template, request
from flask_socketio import SocketIO
from flask_sqlalchemy import SQLAlchemy # Import Flask-SQLAlchemy
from flask_migrate import Migrate # Import Flask-Migrate

from config import Config
from events import register_events

app = Flask(__name__)
app.config.from_object(Config)

# Khởi tạo đối tượng SQLAlchemy và Migrate
db = SQLAlchemy(app)
migrate = Migrate(app, db)

# Định nghĩa Model cho bảng tin nhắn
class Message(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), nullable=False)
    message = db.Column(db.String(500), nullable=False)
    timestamp = db.Column(db.DateTime, default=db.func.now()) # Thời gian tạo tin nhắn

    def __repr__(self):
        return f'<Message {self.username}: {self.message}>'

    # Phương thức để chuyển đổi đối tượng tin nhắn thành từ điển, tiện cho việc gửi qua SocketIO
    def to_dict(self):
        return {
            'username': self.username,
            'message': self.message,
            'timestamp': self.timestamp.isoformat() # Chuyển đổi datetime sang chuỗi ISO 8601
        }

socketio = SocketIO(app)

# Đăng ký các sự kiện SocketIO, truyền đối tượng 'db' vào để các hàm xử lý sự kiện có thể tương tác với DB
register_events(socketio, db)

@app.route('/')
def index():
    return render_template('index.html')

if __name__ == '__main__':
    # *** LƯU Ý: KHÔNG DÙNG db.create_all() trong môi trường production khi dùng Flask-Migrate ***
    # Dòng này chỉ hữu ích khi phát triển cục bộ với SQLite mà không muốn dùng migrations ngay.
    # Khi deploy, Flask-Migrate sẽ lo việc tạo/cập nhật schema.
    # with app.app_context():
    #     db.create_all()

    port = int(os.environ.get('PORT', 5000))
    socketio.run(app, host='0.0.0.0', port=port, debug=Config.DEBUG)