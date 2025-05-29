from flask import request, current_app
from flask_socketio import emit
from datetime import datetime

def register_events(socketio, mongo): # Hàm register_events nhận đối tượng 'mongo'
    messages_collection = mongo.db.messages # Truy cập collection 'messages'

    @socketio.on('message')
    def handle_message(data):
        username = data.get('username', 'Ẩn danh')
        message_content = data.get('message', '')

        if message_content.strip():
            print(f'Tin nhắn từ {username}: {message_content}')

            message_document = {
                'username': username,
                'message': message_content,
                'timestamp': datetime.now()
            }

            messages_collection.insert_one(message_document)

            emittable_message = {
                'username': message_document['username'],
                'message': message_document['message'],
                'timestamp': message_document['timestamp'].isoformat()
            }
            emit('message', emittable_message, broadcast=True)

    @socketio.on('connect')
    def handle_connect():
        print('Client đã kết nối:', request.sid)

        messages_cursor = messages_collection.find().sort('timestamp', -1).limit(50)
        messages_list = list(messages_cursor)
        for msg_doc in reversed(messages_list):
            emittable_message = {
                'username': msg_doc['username'],
                'message': msg_doc['message'],
                'timestamp': msg_doc['timestamp'].isoformat()
            }
            emit('message', emittable_message)

        emit('message', {'username': 'Hệ thống', 'message': f'Một người dùng mới ({request.sid}) đã tham gia.'}, broadcast=True)


    @socketio.on('disconnect')
    def handle_disconnect():
        print('Client đã ngắt kết nối:', request.sid)
        emit('message', {'username': 'Hệ thống', 'message': f'Một người dùng ({request.sid}) đã rời khỏi.'}, broadcast=True)