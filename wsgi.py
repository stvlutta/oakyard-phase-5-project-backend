"""
WSGI entry point for production deployment
"""
from run import app

if __name__ == "__main__":
    app.run()