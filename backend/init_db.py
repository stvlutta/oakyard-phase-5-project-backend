#!/usr/bin/env python3
"""Initialize the database with sample data"""

from app import create_app, db
from app.seed_data import seed_database
import os

def init_database():
    """Initialize database with tables and sample data"""
    app = create_app('development')
    
    with app.app_context():
        # Create all tables
        db.create_all()
        print("Database tables created successfully!")
        
        # Seed with sample data
        seed_database()
        print("Database seeded with sample data!")

if __name__ == '__main__':
    init_database()