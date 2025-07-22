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