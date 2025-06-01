import os
import eventlet

# Apply eventlet monkey patching before importing the application
if os.environ.get('FLASK_ENV') != 'development':
    eventlet.monkey_patch()

# Import the Flask application and SocketIO instance from app.py
from app import app as application, socketio

if __name__ == '__main__':
    # This block is for local testing, not used in production with Gunicorn
    port = int(os.environ.get('PORT', 5000))
    socketio.run(application, host='0.0.0.0', port=port)