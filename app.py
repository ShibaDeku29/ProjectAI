# app.py (Đã sửa lỗi, đảm bảo 2 dòng này đứng đầu tiên)
import eventlet
eventlet.monkey_patch()

import os
from flask import Flask, render_template, request, redirect, url_for, flash
from flask_socketio import SocketIO
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
# Thêm import datetime cho events.py (mặc dù nó được dùng trong events.py, nhưng để đây cho dễ thấy)
from datetime import datetime


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
login_manager.login_view = 'login' # Tên hàm view cho trang đăng nhập

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# Định nghĩa Model cho bảng tin nhắn
class Message(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), nullable=False)
    message = db.Column(db.String(500), nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.now) # Sửa db.func.now() thành datetime.now

    def __repr__(self):
        return f'<Message {self.username}: {self.message}>'

    def to_dict(self):
        return {
            'username': self.username,
            'message': self.message,
            'timestamp': self.timestamp.isoformat()
        }

# Định nghĩa Model cho bảng người dùng
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def __repr__(self):
        return f'<User {self.username}>'


socketio = SocketIO(app)
register_events(socketio, db, current_user)

@app.route('/')
def home():
    """Route cho trang chủ/landing page."""
    return render_template('home.html')

@app.route('/chat')
@login_required # Chỉ cho phép người dùng đã đăng nhập truy cập trang chat
def chat_room(): # Đổi tên hàm từ index thành chat_room
    """Route cho phòng chat chính."""
    return render_template('index.html') # index.html vẫn là giao diện chat

@app.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('chat_room')) # Chuyển hướng đến phòng chat nếu đã đăng nhập

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
    if current_user.is_authenticated:
        return redirect(url_for('chat_room')) # Chuyển hướng đến phòng chat nếu đã đăng nhập

    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')

        user = User.query.filter_by(username=username).first()
        if user and user.check_password(password):
            login_user(user)
            flash('Đăng nhập thành công!', 'success')
            # Chuyển hướng đến trang chat sau khi đăng nhập thành công
            # next_page vẫn được giữ lại nếu người dùng bị chuyển hướng đến login từ một trang yêu cầu login
            next_page = request.args.get('next')
            return redirect(next_page or url_for('chat_room'))
        else:
            flash('Tên người dùng hoặc mật khẩu không đúng!', 'danger')
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('Bạn đã đăng xuất!', 'info')
    return redirect(url_for('home')) # Chuyển hướng về trang chủ sau khi đăng xuất


if __name__ == '__main__':
    # eventlet.monkey_patch() # Đã gọi ở đầu file

    with app.app_context():
        db.create_all()

    port = int(os.environ.get('PORT', 5000))
    # Chạy với reloader=False khi dùng eventlet trong chế độ debug để tránh lỗi
    # Hoặc đảm bảo eventlet.monkey_patch() được gọi rất sớm.
    # Hiện tại đã gọi ở đầu file nên không cần reloader=False một cách cứng nhắc.
    socketio.run(app, host='0.0.0.0', port=port, debug=Config.DEBUG)