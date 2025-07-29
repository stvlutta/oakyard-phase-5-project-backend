from app import create_app, socketio
import os

app = create_app(os.getenv('FLASK_ENV', 'development'))

if __name__ == '__main__':
    debug = os.getenv('FLASK_ENV', 'development') == 'development'
    port = int(os.getenv('PORT', 5000))
    socketio.run(app, debug=debug, host='0.0.0.0', port=port)