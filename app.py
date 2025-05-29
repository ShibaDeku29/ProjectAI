import os
from datetime import datetime
from flask import Flask, render_template, request
from flask_socketio import SocketIO
from flask_pymongo import PyMongo # Import Flask-PyMongo

from config import Config
from events import register_events

app = Flask(__name__)
app.config.from_object(Config)

# Khởi tạo Flask-PyMongo với ứng dụng Flask của bạn
mongo = PyMongo(app)

socketio = SocketIO(app)

# Đăng ký các xử lý sự kiện SocketIO, truyền đối tượng 'mongo' vào để các hàm xử lý có thể tương tác với DB
register_events(socketio, mongo)

@app.route('/')
def index():
    return render_template('index.html')

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    socketio.run(app, host='0.0.0.0', port=port, debug=Config.DEBUG)