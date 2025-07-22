#!/usr/bin/env python3
"""Simple backend startup script"""

import os
import sys
from pathlib import Path

# Add the current directory to Python path
sys.path.insert(0, str(Path(__file__).parent))

# Set environment variables
os.environ['FLASK_ENV'] = 'development'
os.environ['FLASK_DEBUG'] = '1'

def main():
    try:
        # Try to import and run the app
        from app import create_app, socketio
        
        app = create_app('development')

        # Create uploads directory
        os.makedirs('uploads', exist_ok=True)
        
        print("🏢 Oakyard Backend Server")
        print("========================")
        print("🚀 Starting server on http://localhost:5001")
        print("📡 WebSocket support enabled")
        print("🔄 Auto-reload enabled")
        print("\nPress Ctrl+C to stop the server\n")

                # Start server
        socketio.run(app, 
                    host='0.0.0.0', 
                    port=5001, 
                    debug=True,
                    use_reloader=False,  # Disable reloader to avoid issues
                    allow_unsafe_werkzeug=True)
        
    except ImportError as e:
        print(f"❌ Import error: {e}")
        print("Please install requirements: pip install -r requirements.txt")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Failed to start server: {e}")
        sys.exit(1)

if __name__ == '__main__':
    main()