# app.py

# XÓA NHỮNG DÒNG NÀY KHỎI ĐẦU TỆP:
# import eventlet
# eventlet.monkey_patch()

import os
from flask import Flask, render_template, request, redirect, url_for, flash
from flask_socketio import SocketIO
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate # Đảm bảo bạn đã import Migrate
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime # Đảm bảo import datetime

from config import Config # Đảm bảo config.py của bạn đúng tên và vị trí
from events import register_events # events.py không nên gọi monkey_patch() nữa

app = Flask(__name__)
app.config.from_object(Config)

db = SQLAlchemy(app)
migrate = Migrate(app, db) # Khởi tạo Flask-Migrate

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# --- Models ---
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    
    # >>> THÊM CÁC TRƯỜNG MỚI BẠN MUỐN MIGRATE
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    avatar_url = db.Column(db.String(256), nullable=True) # URL tới ảnh đại diện

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def __repr__(self):
        return f'<User {self.username}>'

class Message(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), nullable=False) # Cân nhắc dùng ForeignKey tới User.id
    message = db.Column(db.String(500), nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow, index=True)

    def __repr__(self):
        return f'<Message от {self.username}: {self.message}>' # Sửa lỗi chính tả tiếng Nga nếu có

    def to_dict(self):
        return {
            'username': self.username,
            'message': self.message,
            'timestamp': self.timestamp.isoformat()
        }
# --- End Models ---

# Khởi tạo SocketIO. 
# async_mode='eventlet' có thể được chỉ định rõ ràng nếu bạn muốn, 
# nhưng thường Flask-SocketIO sẽ tự phát hiện nếu eventlet được cài đặt.
socketio = SocketIO(app) 

# Đăng ký các sự kiện SocketIO
# Đảm bảo current_user được truyền vào đây một cách phù hợp.
# Flask-SocketIO có cơ chế session riêng có thể tích hợp với Flask-Login.
if 'register_events' in globals(): # Kiểm tra nếu hàm đã được import
    register_events(socketio, db, current_user)


# --- Routes ---
# (Giữ nguyên các route /, /chat, /register, /login, /logout, /dashboard như đã định nghĩa trước đó)
@app.route('/')
def home():
    return render_template('home.html')

@app.route('/chat')
@login_required
def chat_room():
    return render_template('index.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('chat_room'))
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        user = User.query.filter_by(username=username).first()
        if user:
            flash('Tên người dùng đã tồn tại!', 'danger')
        else:
            new_user = User(username=username)
            new_user.set_password(password)
            # created_at sẽ được đặt giá trị mặc định
            db.session.add(new_user)
            db.session.commit()
            flash('Đăng ký thành công! Vui lòng đăng nhập.', 'success')
            return redirect(url_for('login'))
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('chat_room'))
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        user = User.query.filter_by(username=username).first()
        if user and user.check_password(password):
            login_user(user)
            flash('Đăng nhập thành công!', 'success')
            next_page = request.args.get('next')
            return redirect(next_page or url_for('dashboard')) # Hoặc 'chat_room'
        else:
            flash('Tên người dùng hoặc mật khẩu không đúng!', 'danger')
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('Bạn đã đăng xuất!', 'info')
    return redirect(url_for('home'))

@app.route('/dashboard')
@login_required
def dashboard():
    public_message_count = Message.query.filter_by(username=current_user.username).count()
    return render_template('dashboard.html',
                           username=current_user.username,
                           public_message_count=public_message_count)
# --- End Routes ---


if __name__ == '__main__':
    # >>> CHỈ GỌI MONKEY_PATCH KHI CHẠY APP TRỰC TIẾP VỚI EVENTLET <<<
    import eventlet
    eventlet.monkey_patch()
    
    # Khởi tạo bảng trong lần chạy đầu tiên hoặc khi phát triển đơn giản.
    # Với Flask-Migrate, các thay đổi schema sẽ được quản lý bằng migrations.
    # Cân nhắc bỏ qua db.create_all() nếu bạn hoàn toàn dựa vào migrations.
    # with app.app_context():
    #     db.create_all() 

    port = int(os.environ.get('PORT', 5000))
    # Sử dụng socketio.run() để khởi động máy chủ (bao gồm cả máy chủ WebSocket của SocketIO)
    socketio.run(app, host='0.0.0.0', port=port, debug=app.config.get('DEBUG', False))
