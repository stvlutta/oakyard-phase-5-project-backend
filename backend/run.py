from app import create_app, socketio
import os

app = create_app(os.getenv('FLASK_ENV', 'development'))

if __name__ == '__main__':
    socketio.run(app, debug=True, host='0.0.0.0', port=5000)