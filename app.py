import eventlet # Import eventlet
eventlet.monkey_patch() # Gọi monkey_patch() ngay từ đầu để tránh lỗi context

import os
from flask import Flask, render_template, request, redirect, url_for, flash
from flask_socketio import SocketIO
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash

from config import Config
from events import register_events

app = Flask(__name__)
app.config.from_object(Config)

# Khởi tạo đối tượng SQLAlchemy và Migrate
db = SQLAlchemy(app)
migrate = Migrate(app, db)

# Cấu hình Flask-Login
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login' # Tên hàm view cho trang đăng nhập (sẽ chuyển hướng đến đây nếu chưa đăng nhập)

@login_manager.user_loader
def load_user(user_id):
    """
    Hàm này được Flask-Login sử dụng để tải người dùng từ ID phiên (session ID).
    """
    return User.query.get(int(user_id))

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

# Định nghĩa Model cho bảng người dùng
class User(UserMixin, db.Model): # UserMixin cung cấp các thuộc tính và phương thức cần thiết cho Flask-Login
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(128), nullable=False)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def __repr__(self):
        return f'<User {self.username}>'


socketio = SocketIO(app)

# Đăng ký các sự kiện SocketIO, truyền đối tượng 'db' và 'current_user' để các hàm xử lý sự kiện có thể tương tác với DB và biết người dùng hiện tại
register_events(socketio, db, current_user)

@app.route('/')
@login_required # Chỉ cho phép người dùng đã đăng nhập truy cập trang chat
def index():
    return render_template('index.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated: # Nếu đã đăng nhập, chuyển hướng về trang chat
        return redirect(url_for('index'))

    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')

        user = User.query.filter_by(username=username).first()
        if user:
            flash('Tên người dùng đã tồn tại!', 'danger')
        else:
            new_user = User(username=username)
            new_user.set_password(password)
            db.session.add(new_user)
            db.session.commit()
            flash('Đăng ký thành công! Vui lòng đăng nhập.', 'success')
            return redirect(url_for('login'))
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated: # Nếu đã đăng nhập, chuyển hướng về trang chat
        return redirect(url_for('index'))

    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')

        user = User.query.filter_by(username=username).first()
        if user and user.check_password(password):
            login_user(user) # Đăng nhập người dùng
            flash('Đăng nhập thành công!', 'success')
            next_page = request.args.get('next') # Lấy URL mà người dùng muốn truy cập trước đó (nếu có)
            return redirect(next_page or url_for('index'))
        else:
            flash('Tên người dùng hoặc mật khẩu không đúng!', 'danger')
    return render_template('login.html')

@app.route('/logout')
@login_required # Yêu cầu đăng nhập để đăng xuất
def logout():
    logout_user()
    flash('Bạn đã đăng xuất!', 'info')
    return redirect(url_for('login'))


if __name__ == '__main__':
    # Đảm bảo app_context được tạo để db.create_all() hoạt động
    # Chạy lệnh này để tạo bảng User và Message nếu chưa có (chỉ cho phát triển cục bộ với SQLite)
    # Với PostgreSQL trên Render, bạn sẽ dùng 'flask db upgrade' trong Start Command.
    with app.app_context():
        db.create_all()

    port = int(os.environ.get('PORT', 5000))
    socketio.run(app, host='0.0.0.0', port=port, debug=Config.DEBUG)