import os
from flask import Flask, render_template, request # Cần import 'request'
from flask_socketio import SocketIO, emit

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'super-secret-key-default')
socketio = SocketIO(app)

@app.route('/')
def index():
    return render_template('index.html')

@socketio.on('message')
def handle_message(data):
    username = data.get('username', 'Ẩn danh')
    message = data.get('message', '')

    if message.strip():
        print(f'Tin nhắn từ {username}: {message}')
        emit('message', {'username': username, 'message': message}, broadcast=True)

@socketio.on('connect')
def handle_connect(): # Hàm handle_connect không cần nhận sid nếu bạn dùng request.sid
    """Xử lý các kết nối client mới."""
    # Khi dùng request.sid, nó đã được cung cấp bởi ngữ cảnh của Flask.
    # Tuy nhiên, nếu bạn muốn nhận sid trực tiếp làm tham số, bạn có thể thay đổi thành:
    # def handle_connect(sid):
    #     print('Client đã kết nối:', sid)
    print('Client đã kết nối:', request.sid) # Log kết nối với ID phiên

@socketio.on('disconnect')
def handle_disconnect():
    """Xử lý các ngắt kết nối client."""
    print('Client đã ngắt kết nối:', request.sid) # Log ngắt kết nối với ID phiên

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    socketio.run(app, host='0.0.0.0', port=port, debug=True)