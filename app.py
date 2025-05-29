import os
from flask import Flask, render_template
from flask_socketio import SocketIO, emit

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'super-secret-key') # Use environment variable for secret key
socketio = SocketIO(app)

@app.route('/')
def index():
    return render_template('index.html')

@socketio.on('message')
def handle_message(data):
    """
    Handles incoming messages from clients.
    `data` is expected to be a dictionary with 'username' and 'message' keys.
    """
    username = data.get('username', 'Anonymous')
    message = data.get('message', '')

    if message.strip(): # Ensure message is not empty
        print(f'Message from {username}: {message}')
        emit('message', {'username': username, 'message': message}, broadcast=True) # Emit a dictionary for better structure

@socketio.on('connect')
def handle_connect():
    """Handles new client connections."""
    print('Client connected:', request.sid) # Log connection with session ID
    # Optionally, emit a system message to all clients about a new user
    # emit('message', {'username': 'System', 'message': 'A new user has joined the chat.'}, broadcast=True)

@socketio.on('disconnect')
def handle_disconnect():
    """Handles client disconnections."""
    print('Client disconnected:', request.sid) # Log disconnection with session ID
    # Optionally, emit a system message to all clients about a user leaving
    # emit('message', {'username': 'System', 'message': 'A user has left the chat.'}, broadcast=True)

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000)) # Changed default port to 5000, common for Flask
    socketio.run(app, host='0.0.0.0', port=port, debug=True) # Enable debug mode for development