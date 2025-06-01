import os
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
from flask_socketio import SocketIO
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
from sqlalchemy import MetaData

from config import Config
from events import register_events

# Define naming convention for Alembic migrations
metadata = MetaData(
    naming_convention={
        "ix": 'ix_%(column_0_label)s',
        "uq": "uq_%(table_name)s_%(column_0_name)s",
        "ck": "ck_%(table_name)s_%(constraint_name)s",
        "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
        "pk": "pk_%(table_name)s"
    }
)

app = Flask(__name__)
app.config.from_object(Config)

# Initialize SQLAlchemy without metadata_obj
db = SQLAlchemy(app)

migrate = Migrate(app, db, render_as_batch=True)

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'
login_manager.login_message = "Vui lòng đăng nhập để truy cập trang này."
login_manager.login_message_category = "info"

@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))

# --- Models ---
class User(UserMixin, db.Model):
    __tablename__ = 'user'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(256), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    avatar_url = db.Column(db.String(256), nullable=True, default='https://placehold.co/120x120/007bff/ffffff?text=User')
    email = db.Column(db.String(120), unique=True, nullable=True, index=True)
    full_name = db.Column(db.String(120), nullable=True)
    bio = db.Column(db.Text, nullable=True)
    last_seen = db.Column(db.DateTime, default=datetime.utcnow)

    notifications = db.relationship('Notification', backref='recipient_user', lazy='dynamic', foreign_keys='Notification.user_id')
    activities = db.relationship('UserActivity', backref='actor_user', lazy='dynamic', foreign_keys='UserActivity.user_id')
    friendships_a = db.relationship('Friendship', foreign_keys='Friendship.user_a_id', backref='user_a', lazy='dynamic')
    friendships_b = db.relationship('Friendship', foreign_keys='Friendship.user_b_id', backref='user_b', lazy='dynamic')

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)
    
    def ping(self):
        self.last_seen = datetime.utcnow()
        db.session.add(self)

    def __repr__(self):
        return f'<User {self.username}>'

class Message(db.Model):
    __tablename__ = 'message'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), nullable=False)
    message_content = db.Column(db.Text, nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    is_private = db.Column(db.Boolean, default=False)
    recipient_username = db.Column(db.String(80), nullable=True)

    def __repr__(self):
        return f'<Message ID {self.id} from {self.username}>'

    def to_dict(self):
        return {
            'id': self.id,
            'username': self.username,
            'message': self.message_content,
            'timestamp': self.timestamp.isoformat(),
            'private': self.is_private,
            'recipient': self.recipient_username
        }

class Friendship(db.Model):
    __tablename__ = 'friendship'
    user_a_id = db.Column(db.Integer, db.ForeignKey('user.id', name='fk_friendship_user_a_id_user'), primary_key=True)
    user_b_id = db.Column(db.Integer, db.ForeignKey('user.id', name='fk_friendship_user_b_id_user'), primary_key=True)
    status = db.Column(db.String(30), nullable=False, default='pending_a_to_b')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    accepted_at = db.Column(db.DateTime, nullable=True)

    def __repr__(self):
        return f'<Friendship ({self.user_a_id}, {self.user_b_id}) - {self.status}>'

class Notification(db.Model):
    __tablename__ = 'notification'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id', name='fk_notification_user_id_user'), nullable=False, index=True)
    name = db.Column(db.String(128), nullable=False)
    payload_json = db.Column(db.Text, nullable=True)
    is_read = db.Column(db.Boolean, default=False, index=True)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow, index=True)

    def get_payload(self):
        import json
        if self.payload_json:
            try:
                return json.loads(self.payload_json)
            except json.JSONDecodeError:
                return None
        return None

    def __repr__(self):
        return f'<Notification {self.name} for User {self.user_id}>'

class UserActivity(db.Model):
    __tablename__ = 'user_activity'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id', name='fk_useractivity_user_id_user'), nullable=False, index=True)
    activity_type = db.Column(db.String(50), nullable=False)
    description = db.Column(db.Text, nullable=True)
    target_user_id = db.Column(db.Integer, db.ForeignKey('user.id', name='fk_useractivity_target_user_id_user'), nullable=True)
    target_message_id = db.Column(db.Integer, db.ForeignKey('message.id', name='fk_useractivity_target_message_id_message'), nullable=True)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow, index=True)

    def __repr__(self):
        return f'<UserActivity {self.activity_type} by User {self.user_id} at {self.timestamp}>'

# --- End Models ---

socketio = SocketIO(app)
if 'register_events' in globals():
    register_events(socketio, db, current_user)

# --- Routes ---
@app.before_request
def before_request_hook():
    if current_user.is_authenticated:
        current_user.ping()

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
        email = request.form.get('email', '').strip()
        full_name = request.form.get('full_name', '').strip()

        if not username or not password:
            flash('Tên người dùng và mật khẩu là bắt buộc!', 'danger')
            return render_template('register.html', username=username, email=email, full_name=full_name)

        user_by_username = User.query.filter_by(username=username).first()
        user_by_email = None
        if email:
            user_by_email = User.query.filter_by(email=email).first()

        if user_by_username:
            flash('Tên người dùng đã tồn tại!', 'danger')
        elif email and user_by_email:
            flash('Địa chỉ email này đã được sử dụng!', 'danger')
        else:
            new_user = User(username=username, email=email if email else None, full_name=full_name if full_name else None)
            new_user.set_password(password)
            db.session.add(new_user)
            try:
                db.session.commit()
                activity = UserActivity(user_id=new_user.id, activity_type='registered', description=f'User {new_user.username} registered.')
                db.session.add(activity)
                db.session.commit()
                flash('Đăng ký thành công! Vui lòng đăng nhập.', 'success')
                return redirect(url_for('login'))
            except Exception as e:
                db.session.rollback()
                flash(f'Đã xảy ra lỗi khi đăng ký: {e}', 'danger')
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
            login_user(user, remember=request.form.get('remember_me') == 'on')
            activity = UserActivity(user_id=user.id, activity_type='logged_in', description=f'User {user.username} logged in.')
            db.session.add(activity)
            db.session.commit()
            flash('Đăng nhập thành công!', 'success')
            next_page = request.args.get('next')
            return redirect(next_page or url_for('dashboard'))
        else:
            flash('Tên người dùng hoặc mật khẩu không đúng!', 'danger')
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    user_id = current_user.id
    username = current_user.username
    logout_user()
    activity = UserActivity(user_id=user_id, activity_type='logged_out', description=f'User {username} logged out.')
    db.session.add(activity)
    db.session.commit()
    flash('Bạn đã đăng xuất!', 'info')
    return redirect(url_for('home'))

@app.route('/dashboard')
@login_required
def dashboard():
    public_message_count = Message.query.filter_by(username=current_user.username, is_private=False).count()
    recent_activities = UserActivity.query.filter_by(user_id=current_user.id).order_by(UserActivity.timestamp.desc()).limit(5).all()
    unread_notifications_count = Notification.query.filter_by(user_id=current_user.id, is_read=False).count()
    friend_requests = Friendship.query.filter_by(user_b_id=current_user.id, status='pending_a_to_b').count()
    return render_template('dashboard.html',
                           public_message_count=public_message_count,
                           recent_activities=recent_activities,
                           unread_notifications_count=unread_notifications_count,
                           friend_requests=friend_requests)

@app.route('/profile/edit', methods=['GET', 'POST'])
@login_required
def edit_profile():
    if request.method == 'POST':
        full_name = request.form.get('full_name', '').strip()
        email = request.form.get('email', '').strip()
        bio = request.form.get('bio', '').strip()
        avatar_url = request.form.get('avatar_url', '').strip()

        if email and User.query.filter_by(email=email).first() and email != current_user.email:
            flash('Email này đã được sử dụng!', 'danger')
            return render_template('edit_profile.html', full_name=full_name, email=email, bio=bio, avatar_url=avatar_url)

        current_user.full_name = full_name if full_name else None
        current_user.email = email if email else None
        current_user.bio = bio if bio else None
        current_user.avatar_url = avatar_url if avatar_url else current_user.avatar_url

        try:
            db.session.commit()
            activity = UserActivity(user_id=current_user.id, activity_type='updated_profile', description=f'User {current_user.username} updated their profile.')
            db.session.add(activity)
            db.session.commit()
            flash('Cập nhật hồ sơ thành công!', 'success')
            return redirect(url_for('dashboard'))
        except Exception as e:
            db.session.rollback()
            flash(f'Lỗi khi cập nhật hồ sơ: {e}', 'danger')
    return render_template('edit_profile.html', full_name=current_user.full_name, email=current_user.email, bio=current_user.bio, avatar_url=current_user.avatar_url)

@app.route('/notifications')
@login_required
def notifications():
    notifications = Notification.query.filter_by(user_id=current_user.id).order_by(Notification.timestamp.desc()).all()
    return render_template('notifications.html', notifications=notifications)

@app.route('/notifications/mark_read/<int:notification_id>', methods=['POST'])
@login_required
def mark_notification_read(notification_id):
    notification = Notification.query.get_or_404(notification_id)
    if notification.user_id != current_user.id:
        return jsonify({'error': 'Unauthorized'}), 403
    notification.is_read = True
    db.session.commit()
    return jsonify({'success': True})

@app.route('/friends')
@login_required
def friends():
    friend_requests = Friendship.query.filter_by(user_b_id=current_user.id, status='pending_a_to_b').all()
    friends = Friendship.query.filter(
        ((Friendship.user_a_id == current_user.id) | (Friendship.user_b_id == current_user.id)) & 
        (Friendship.status == 'friends')
    ).all()
    return render_template('friends.html', friend_requests=friend_requests, friends=friends)

@app.route('/friends/request/<string:username>', methods=['POST'])
@login_required
def send_friend_request(username):
    target_user = User.query.filter_by(username=username).first()
    if not target_user:
        flash('Người dùng không tồn tại!', 'danger')
        return redirect(url_for('friends'))
    if target_user.id == current_user.id:
        flash('Không thể gửi lời mời kết bạn cho chính mình!', 'danger')
        return redirect(url_for('friends'))
    
    existing_friendship = Friendship.query.filter_by(user_a_id=current_user.id, user_b_id=target_user.id).first()
    if existing_friendship:
        flash('Lời mời kết bạn đã tồn tại hoặc đã là bạn!', 'info')
        return redirect(url_for('friends'))

    friendship = Friendship(user_a_id=current_user.id, user_b_id=target_user.id, status='pending_a_to_b')
    notification = Notification(
        user_id=target_user.id,
        name='friend_request_received',
        payload_json=f'{{"from_username": "{current_user.username}"}}'
    )
    db.session.add(friendship)
    db.session.add(notification)
    try:
        db.session.commit()
        flash('Gửi lời mời kết bạn thành công!', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Lỗi khi gửi lời mời: {e}', 'danger')
    return redirect(url_for('friends'))

@app.route('/friends/accept/<int:user_id>', methods=['POST'])
@login_required
def accept_friend_request(user_id):
    friendship = Friendship.query.filter_by(user_a_id=user_id, user_b_id=current_user.id, status='pending_a_to_b').first()
    if not friendship:
        flash('Lời mời kết bạn không tồn tại!', 'danger')
        return redirect(url_for('friends'))
    
    friendship.status = 'friends'
    friendship.accepted_at = datetime.utcnow()
    notification = Notification(
        user_id=user_id,
        name='friend_request_accepted',
        payload_json=f'{{"from_username": "{current_user.username}"}}'
    )
    db.session.add(notification)
    try:
        db.session.commit()
        flash('Đã chấp nhận lời mời kết bạn!', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Lỗi khi chấp nhận lời mời: {e}', 'danger')
    return redirect(url_for('friends'))

@app.route('/settings', methods=['GET', 'POST'])
@login_required
def settings():
    if request.method == 'POST':
        new_password = request.form.get('new_password')
        if new_password:
            current_user.set_password(new_password)
            try:
                db.session.commit()
                flash('Đổi mật khẩu thành công!', 'success')
                return redirect(url_for('settings'))
            except Exception as e:
                db.session.rollback()
                flash(f'Lỗi khi đổi mật khẩu: {e}', 'danger')
    return render_template('settings.html')

@app.route('/security')
@login_required
def security():
    return render_template('security.html')

# --- End Routes ---

if __name__ == '__main__':
    if os.environ.get('WERKZEUG_RUN_MAIN') != 'true':
        try:
            import eventlet
            eventlet.monkey_patch()
            print("Eventlet monkey patching applied.")
        except ImportError:
            print("Eventlet not found, running without monkey patching.")
            pass
    
    port = int(os.environ.get('PORT', 5000))
    debug_mode = app.config.get('DEBUG', False)
    socketio.run(app, host='0.0.0.0', port=port, debug=debug_mode, use_reloader=debug_mode)