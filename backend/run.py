from app import create_app, socketio
import os

app = create_app(os.getenv('FLASK_ENV', 'development'))