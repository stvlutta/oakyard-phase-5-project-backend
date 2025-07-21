#!/usr/bin/env python3
"""Development server startup script"""

import os
import sys
import subprocess
from pathlib import Path

def check_redis():
    """Check if Redis is running"""
    try:
        import redis
        r = redis.Redis(host='localhost', port=6379, db=0)
        r.ping()
        return True
    except:
        return False
    
def install_requirements():
    """Install Python requirements"""
    print("Installing Python dependencies...")
    try:
        subprocess.run([sys.executable, '-m', 'pip', 'install', '-r', 'requirements.txt'], 
                      check=True, capture_output=True)
        print("✅ Dependencies installed successfully!")
    except subprocess.CalledProcessError as e:
        print(f"❌ Failed to install dependencies: {e}")
        return False
    return True

def setup_database():
    """Set up the database"""
    print("Setting up database...")
    try:
        # Import here to avoid issues if dependencies aren't installed yet
        from app import create_app, db
        from app.seed_data import seed_database
        
        app = create_app('development')
        with app.app_context():
            # Check if database exists and has tables
            try:
                from app.models.user import User
                user_count = User.query.count()
                print(f"✅ Database already exists with {user_count} users")
                return True
            except:
                # Database doesn't exist or is empty, create it
                print("Creating database tables...")
                db.create_all()
                
                print("Seeding database with sample data...")
                seed_database()
                print("✅ Database setup complete!")
                return True
    except Exception as e:
        print(f"❌ Database setup failed: {e}")
        return False
    
def start_server():
    """Start the development server"""
    print("Starting Flask development server...")
    
    # Set environment variables
    os.environ['FLASK_ENV'] = 'development'
    os.environ['FLASK_DEBUG'] = '1'
    
    try:
        from app import create_app, socketio
        app = create_app('development')
        
        print("🚀 Starting server on http://localhost:5000")
        print("📡 WebSocket support enabled")
        print("🔄 Auto-reload enabled")
        print("\nPress Ctrl+C to stop the server")
        
        # Start with SocketIO support
        socketio.run(app, 
                    host='0.0.0.0', 
                    port=5000, 
                    debug=True,
                    use_reloader=True,
                    allow_unsafe_werkzeug=True)
        
    except Exception as e:
        print(f"❌ Failed to start server: {e}")
        return False
