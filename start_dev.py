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